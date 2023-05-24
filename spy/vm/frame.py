from spy.vm.vm import SPyVM
from spy.vm.object import W_Object, W_i32
from spy.vm.codeobject import W_CodeObject

class BytecodeError(Exception):
    pass

class Frame:
    vm: SPyVM
    w_code: W_CodeObject
    pc: int
    stack: list[W_Object]

    def __init__(self, vm: SPyVM, w_code: W_Object) -> None:
        assert isinstance(w_code, W_CodeObject)
        self.vm = vm
        self.w_code = w_code
        self.pc = 0  # program counter
        self.stack = []

    def push(self, w_value: W_Object) -> None:
        assert isinstance(w_value, W_Object)
        self.stack.append(w_value)

    def pop(self) -> W_Object:
        return self.stack.pop()

    def eval(self) -> W_Object:
        while True:
            op = self.w_code.body[self.pc]
            # 'return' is special, handle it explicitly
            if op.name == 'return':
                ## if len(self.stack) != 1:
                ##     raise BytecodeError(f'Unexpected stack length: {len(self.stack)}')
                return self.pop()
            else:
                meth_name = f'op_{op.name}'
                meth = getattr(self, meth_name, None)
                if meth is None:
                    raise NotImplementedError(meth_name)
                meth(*op.args)
                self.pc += 1

    def op_i32_const(self, w_const: W_Object):
        assert isinstance(w_const, W_i32)
        self.push(w_const)

    def op_i32_add(self):
        w_b = self.pop()
        w_a = self.pop()
        assert isinstance(w_a, W_i32)
        assert isinstance(w_b, W_i32)
        a = self.vm.unwrap(w_a)
        b = self.vm.unwrap(w_b)
        w_c = self.vm.wrap(a + b)
        self.push(w_c)
