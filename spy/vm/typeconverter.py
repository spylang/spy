from typing import TYPE_CHECKING, ClassVar
from dataclasses import dataclass
from spy import ast
from spy.fqn import FQN
from spy.vm.object import W_Object, W_Type
from spy.vm.b import B, OP
from spy.vm.function import W_FuncType
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

@dataclass
class TypeConverter:
    """
    Base class to represent a type conversion step.
    """
    color: ClassVar[str] = None # type: ignore # must be set by subclasses
    w_type: W_Type              # the desired type after the conversion

    def convert(self, vm: 'SPyVM', w_obj: W_Object) -> W_Object:
        """
        Convert w_obj to the desired type.

        The invariant is that the result of convert() must pass a
        vm.typecheck(..., self.w_type) check.
        """
        raise NotImplementedError

    def redshift(self, vm: 'SPyVM', expr: ast.Expr) -> ast.Expr:
        return expr

class DynamicCast(TypeConverter):
    """
    This doesn't actually perform any active "conversion", it just checks at
    runtime that the given object is an instance of the desired type.
    """
    color = 'blue'

    def convert(self, vm: 'SPyVM', w_obj: W_Object) -> W_Object:
        w_from_dynamic_T = vm.call(OP.w_from_dynamic, [self.w_type])
        return vm.call(w_from_dynamic_T, [w_obj])


@dataclass
class NumericConv(TypeConverter):
    """
    Convert between numeric types.

    At the moment, the only supported conversions are i32->f64 and i32->bool,
    and they are hard-coded
    """
    color = 'blue'
    w_fromtype: W_Type

    def convert(self, vm: 'SPyVM', w_obj: W_Object) -> W_Object:
        impls_w = {
            (B.w_i32, B.w_f64): OP.w_i32_to_f64,
            (B.w_i32, B.w_bool): OP.w_i32_to_bool
        }
        w_impl = impls_w[(self.w_fromtype, self.w_type)]
        return vm.call(w_impl, [w_obj])


@dataclass
class JsRefConv(TypeConverter):
    color = 'red'
    w_fromtype: W_Type

    def convert(self, vm: 'SPyVM', w_obj: W_Object) -> W_Object:
        raise NotImplementedError('only C backend so far')

    def redshift(self, vm: 'SPyVM', expr: ast.Expr) -> ast.Expr:
        if self.w_fromtype is B.w_str:
            f = 'jsffi::js_string'
        elif self.w_fromtype is B.w_i32:
            f = 'jsffi::js_i32'
        elif self.w_fromtype == W_FuncType.parse('def() -> void'):
            f = 'jsffi::js_wrap_func'
        else:
            assert False

        return ast.Call(
            loc = expr.loc,
            func = ast.FQNConst(
                loc = expr.loc,
                fqn = FQN(f)
            ),
            args = [expr]
        )
