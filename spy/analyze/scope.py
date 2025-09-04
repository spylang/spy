from typing import Optional
from spy import ast
from spy.location import Loc
from spy.analyze.symtable import Color, VarKind, VarStorage
from spy.fqn import FQN
from spy.errors import SPyError
from spy.analyze.symtable import SymTable, Symbol
from spy.vm.vm import SPyVM


class ScopeAnalyzer:
    """
    Visit the given AST Module and determine the scope of each name.

    The scoping rules for SPy are very simple for now:

      - names defined at module-level scopes are always available to all
        their inner scopes

      - inside a function, assigment defines a local variable ONLY if this
        name does not exist in an outer scope. Note that this is different
        from Python rules. No more 'global' and 'nonlocal' declarations.

      - shadowing a name is an error

    In the future, we might want to introduce a special compatibility mode to
    use Python's rules to make porting easier, e.g. by using `from __python__
    import scoping_rules`, but for now it's not a priority.

    The analyzer operates in two passes:

      1. declare: find all the statements which introduce new symbols (such as
         VarDef, Assign, FuncDef, etc.). At the end of the declare() pass,
         each symtable contains all the names which are directly defined in
         that scope (i.e., sym.level == 0).

      2. flatten: for each usage of a name, determine in which scope the
         definition reside (either the current or an outer one). At the end of
         the flatten() pass, each symtable contains all the names which are
         defined or referenced in that scope.
    """
    vm: SPyVM
    mod: ast.Module
    stack: list[SymTable]
    inner_scopes: dict[ast.FuncDef|ast.ClassDef, SymTable]

    def __init__(self, vm: SPyVM, modname: str, mod: ast.Module) -> None:
        self.vm = vm
        self.mod = mod
        self.builtins_scope = SymTable.from_builtins(vm)
        self.mod_scope = SymTable(modname, 'blue')
        self.stack = []
        self.inner_scopes = {}
        self.push_scope(self.builtins_scope)
        self.push_scope(self.mod_scope)


    # ===============
    # public API
    # ================

    def analyze(self) -> None:
        assert len(self.stack) == 2 # [builtins, module]
        for decl in self.mod.decls:
            self.declare(decl)
        assert len(self.stack) == 2

        for decl in self.mod.decls:
            self.flatten(decl)
        assert len(self.stack) == 2

    def by_module(self) -> SymTable:
        return self.mod_scope

    def by_funcdef(self, funcdef: ast.FuncDef) -> SymTable:
        return self.inner_scopes[funcdef]

    def by_classdef(self, classdef: ast.ClassDef) -> SymTable:
        return self.inner_scopes[classdef]

    def pp(self) -> None:
        self.by_module().pp()
        print()
        for key, symtable in self.inner_scopes.items():
            symtable.pp()
            print()

    # =====

    def new_SymTable(self, name: str, color: Color) -> SymTable:
        """
        Create a new SymTable whose name is derived from its parent
        """
        parent = self.stack[-1].name
        fullname = f'{parent}::{name}'
        return SymTable(fullname, color)

    def push_scope(self, scope: SymTable) -> None:
        self.stack.append(scope)

    def pop_scope(self) -> SymTable:
        return self.stack.pop()

    @property
    def scope(self) -> SymTable:
        """
        Return the currently active scope
        """
        return self.stack[-1]

    def lookup_ref(self, name: str) -> tuple[int, Optional[SymTable], Optional[Symbol]]:
        """
        Lookup a name reference, starting from the innermost scope,
        towards the outer.
        """
        for level, scope in enumerate(reversed(self.stack)):
            if sym := scope.lookup_maybe(name):
                return level, scope, sym
        # not found
        return -1, None, None

    def lookup_definition(self, name: str) -> tuple[int, Optional[Symbol]]:
        """
        Lookup a name definition, starting from the innermost scope,
        towards the output.
        """
        for level, scope in enumerate(reversed(self.stack)):
            if sym := scope.lookup_definition_maybe(name):
                return level, sym
        # not found
        return -1, None

    def define_name(self,
                    name: str,
                    color: ast.Color,
                    varkind: VarKind,
                    loc: Loc,
                    type_loc: Loc,
                    *,
                    fqn: Optional[FQN] = None
                    ) -> None:
        """
        Add a name definition to the current scope.

        The level of the new symbol will be 0.
        """
        level, scope, sym = self.lookup_ref(name)
        if sym and name != '@return':
            assert scope is not None
            if level == 0 and scope.color == 'blue':
                # this happens if we have e.g. the same name defined in two
                # branches of an "if".
                # Note that if the redeclaration happens at runtime, it's
                # still an error, but it's caught by astframe.
                return

            elif level == 0:
                # re-declaration in the same scope
                msg = f'variable `{name}` already declared'

            else:
                # shadowing a name in an outer scope
                msg = (f'variable `{name}` shadows a name declared ' +
                       "in an outer scope")
            err = SPyError('W_ScopeError', msg)
            err.add('error', 'this is the new declaration', loc)
            err.add('note', 'this is the previous declaration', sym.loc)
            raise err

        if fqn is None and self.scope is self.mod_scope:
            # this is a module-level global. Let's give it a FQN
            fqn = FQN([self.mod_scope.name, name])

        # Determine storage type: module-level vars use "cell", others use "direct"
        storage: VarStorage
        if self.scope is self.mod_scope and varkind == 'var':
            storage = 'cell'
        else:
            storage = 'direct'

        sym = Symbol(name, color, varkind, storage, loc=loc, type_loc=type_loc, fqn=fqn, level=0)
        self.scope.add(sym)

    # ====

    def declare(self, node: ast.Node) -> None:
        """
        Visit all the nodes which introduce a new name in the scope, and
        add symbol definitions to the corresponding symtable.
        """
        return node.visit('declare', self)

    def declare_Import(self, imp: ast.Import) -> None:
        w_obj = self.vm.lookup_global(imp.fqn)
        if w_obj is not None:
            self.define_name(imp.asname, 'blue', 'const', imp.loc, imp.loc, fqn=imp.fqn)
            return
        #
        err = SPyError(
            'W_ImportError',
            f'cannot import `{imp.fqn.spy_name}`',
        )
        if imp.fqn.modname not in self.vm.modules_w:
            # See if there is a matching .py file
            if self.vm.find_file_on_path(
                imp.fqn.modname, allow_py_files=True
            ):
                err.add(
                    "error",
                    f"file `{imp.fqn.modname}.py` exists, but py files cannot be imported",
                    loc=imp.loc,
                )
            else:
                # module not found
                err.add(
                    "error", f"module `{imp.fqn.modname}` does not exist", loc=imp.loc
                )
        else:
            # attribute not found
            attr = str(imp.fqn.symbol_name)
            err.add('error',
                    f'attribute `{attr}` does not exist ' +
                    f'in module `{imp.fqn.modname}`',
                    loc=imp.loc_asname)
        raise err

    def declare_GlobalVarDef(self, decl: ast.GlobalVarDef) -> None:
        color: Color
        if decl.vardef.kind == 'var':
            color = 'red'
        else:
            color = 'blue'
        self.define_name(decl.vardef.name, color, decl.vardef.kind, decl.loc,
                         decl.vardef.type.loc)

    def declare_VarDef(self, vardef: ast.VarDef) -> None:
        assert vardef.kind == 'var'
        self.define_name(vardef.name, 'red', vardef.kind, vardef.loc, vardef.type.loc)

    def declare_FuncDef(self, funcdef: ast.FuncDef) -> None:
        # declare the func in the "outer" scope
        self.define_name(funcdef.name, 'blue', 'const', funcdef.prototype_loc,
                         funcdef.prototype_loc)
        # add function arguments to the "inner" scope
        scope_color = funcdef.color
        inner_scope = self.new_SymTable(funcdef.name, scope_color)
        self.push_scope(inner_scope)
        self.inner_scopes[funcdef] = inner_scope
        for arg in funcdef.args:
            self.define_name(arg.name, scope_color, 'var', arg.loc, arg.type.loc)
        if funcdef.vararg:
            self.define_name(funcdef.vararg.name, scope_color, 'var', funcdef.vararg.loc, funcdef.vararg.type.loc)
        self.define_name('@return', scope_color, 'var', funcdef.return_type.loc,
                         funcdef.return_type.loc)
        for stmt in funcdef.body:
            self.declare(stmt)
        self.pop_scope()

    def declare_ClassDef(self, classdef: ast.ClassDef) -> None:
        # declare the class in the "outer" scope
        self.define_name(classdef.name, 'blue', 'const', classdef.loc, classdef.loc)
        inner_scope = self.new_SymTable(classdef.name, 'blue')
        self.push_scope(inner_scope)
        self.inner_scopes[classdef] = inner_scope
        for vardef in classdef.fields:
            self.declare_VarDef(vardef)
        for stmt in classdef.body:
            self.declare(stmt)
        self.pop_scope()

    def declare_Assign(self, assign: ast.Assign) -> None:
        self._declare_target_maybe(assign.target, assign.value)

    def declare_UnpackAssign(self, unpack: ast.UnpackAssign) -> None:
        for target in unpack.targets:
            self._declare_target_maybe(target, unpack.value)

    def _declare_target_maybe(self, target: ast.StrConst,
                              value: ast.Expr) -> None:
        # if target name does not exist elsewhere, we treat it as an implicit
        # declaration
        level, scope, sym = self.lookup_ref(target.value)
        if sym is None:
            # we don't have an explicit type annotation: we consider the
            # "value" to be the type_loc, because it's where the type will be
            # computed from
            type_loc = value.loc
            self.define_name(target.value, 'red', 'var', target.loc, type_loc)

    # ===

    def capture_maybe(self, varname: str) -> None:
        level, _, _ = self.lookup_ref(varname)
        if level in (-1, 0):
            # name already in the symtable, or NameError. Nothing to do here.
            return
        # the name was found but in an outer scope. Let's "capture" it.
        #
        # find the defintion
        level, sym = self.lookup_definition(varname)
        assert sym
        new_sym = sym.replace(level=level)
        assert not self.scope.has_definition(varname)
        self.scope.add(new_sym)

    def flatten(self, node: ast.Node) -> None:
        """
        Visit all the nodes in the AST and flatten the symtables of all the
        FuncDefs.

        In particular, introduce a symbol for every Name which is used inside
        a function but defined in some outer scope.
        """
        return node.visit('flatten', self)

    def flatten_FuncDef(self, funcdef: ast.FuncDef) -> None:
        # the TYPES of the arguments are evaluated in the outer scope
        self.flatten(funcdef.return_type)
        for arg in funcdef.args:
            self.flatten(arg)
        if funcdef.vararg:
            self.flatten(funcdef.vararg)
        #
        # the statements of the function are evaluated in the inner scope
        inner_scope = self.by_funcdef(funcdef)
        self.push_scope(inner_scope)
        for stmt in funcdef.body:
            self.flatten(stmt)
        self.pop_scope()
        #
        funcdef.symtable = inner_scope

    def flatten_ClassDef(self, classdef: ast.ClassDef) -> None:
        inner_scope = self.by_classdef(classdef)
        self.push_scope(inner_scope)
        for vardef in classdef.fields:
            self.flatten(vardef)
        for stmt in classdef.body:
            self.flatten(stmt)
        self.pop_scope()
        #
        classdef.symtable = inner_scope

    def flatten_GlobalVarDef(self, globalvardef: ast.GlobalVarDef) -> None:
        self.flatten(globalvardef.vardef)
        if assign := globalvardef.assign:
            self.capture_maybe(assign.target.value)
            self.flatten(assign.value)

    def flatten_Name(self, name: ast.Name) -> None:
        self.capture_maybe(name.id)

    def flatten_Assign(self, assign: ast.Assign) -> None:
        # Check if we're trying to assign to a const variable
        target_name = assign.target.value
        level, scope, sym = self.lookup_ref(target_name)
        if sym and sym.varkind == 'const':
            # Trying to assign to a const variable - this is an error
            err = SPyError('W_ScopeError', 'invalid assignment target')
            err.add('error', f'{target_name} is const', assign.target.loc)
            err.add('note', 'const declared here', sym.loc)
            err.add('note', f'help: declare it as variable: `var {target_name} ...`', sym.loc)
            raise err

        self.capture_maybe(assign.target.value)
        self.flatten(assign.value)
