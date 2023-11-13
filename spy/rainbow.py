from spy.fqn import FQN
from spy.vm.vm import SPyVM
from spy.vm.object import W_Type
from spy.vm.codeobject import W_CodeObject
from spy.vm.function import W_UserFunction

class RainbowInterpreter:
    """
    Perform typecheck and partial evaluation on the given function object.

    Return a new function object where all blue ops have been evaluated.
    """
    typestack_w: list[W_Type]

    def __init__(self, vm: SPyVM, w_func: W_UserFunction):
        self.vm = vm
        self.w_func = w_func
        self.code= w_func.w_code
        self.code_out = W_CodeObject(
            FQN('rainbow::test'),
            w_functype = w_func.w_functype,
            filename = w_func.w_code.filename,
            lineno = w_func.w_code.lineno)

        self.typestack_w = []
        ## self.blueframe = Frame(w_func)
        ## self.label_maps = []
        ## self.unique_id = 0

    def pushtype(self, w_type: W_Type) -> None:
        self.typestack_w.append(w_type)

    def poptype(self) -> W_Type:
        return self.typestack_w.pop()

    def emit(self, op):
        ## if self.label_maps:
        ##     op = op.relabel(self.label_maps[-1])
        self.code_out.body.append(op)

    def flush(self):
        # XXX implement me
        pass

    def run(self):
        """
        Do abstract interpretation of the whole code
        """
        self.run_range(0, len(self.code.body))
        return W_UserFunction(self.code_out)

    def run_range(self, pc_start, pc_end):
        """
        Do abstract interpretation of the given code range
        """
        pc = pc_start
        while pc < pc_end:
            pc = self.run_single_op(pc)
        self.flush()

    def run_single_op(self, pc):
        """
        Do abstract interpretation of the op at the given PC.

        Return the PC of the operation to execute next.
        """
        op = self.code.body[pc].copy()
        meth = getattr(self, f'op_{op.name}', self.op_default)
        pc_next = meth(pc, op, *op.args)
        if pc_next is None:
            return pc + 1
        else:
            assert type(pc_next) is int
            return pc_next

    def op_default(self, pc, op, *args):
        raise NotImplementedError(f'op_{op.name}')
        ## if self.is_blue(op):
        ##     return self.op_blue(pc, op, *args)
        ## else:
        ##     return self.op_red(pc, op, *args)

    def op_load_const(self, pc, op, w_value):
        w_type = self.vm.dynamic_type(w_value)
        self.pushtype(w_type)
        self.emit(op)

    def op_return(self, pc, op):
        w_type = self.poptype()
        # XXX this should be turned into a proper error
        # XXX 2: we should use is_compatible_type
        assert w_type == self.w_func.w_functype.w_restype
        self.emit(op)
