from spy.vm.opcode import CodeObject
from spy.vm.objects import W_Object, W_i32

class BytecodeError(Exception):
    pass

class Frame:

    def __init__(self, vm, code):
        assert isinstance(code, CodeObject)
        self.vm = vm
        self.code = code
        self.pc = 0  # program counter
        self.stack = []

    def push(self, w_value):
        assert isinstance(w_value, W_Object)
        self.stack.append(w_value)

    def pop(self):
        return self.stack.pop()

    def eval(self):
        while True:
            op = self.code.body[self.pc]
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

    def op_i32_const(self, w_const):
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
