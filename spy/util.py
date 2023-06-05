class MagicExtend:
    """
    Create a magic @extend decorator which allows to easily monkey patch
    classes of a given module. The intended usage is the following:

    # in module a.py
    from .util import MagicExtend

    extend = MagicExtend()

    @extend.register
    class Foo:
        pass

    @extend.register
    class Bar:
        pass

    # in module b.py
    import a
    @a.extend
    class Foo:
        x = 42

    @a.extend
    class Bar:
        y = 43
    """
    modname: str
    classes: dict[str, type]

    def __init__(self, modname: str) -> None:
        self.modname = modname
        self.classes = {}

    def __repr__(self) -> str:
        return f'<MagicExtend {self.modname!r}>'

    def register(self, cls: type) -> type:
        self.classes[cls.__name__] = cls
        return cls

    def __call__(self, new_class: type) -> type:
        """
        This is the @extend decorator
        """
        name = new_class.__name__
        if name not in self.classes:
            raise AttributeError(f'class {name} is not registered as extendable')
        cls = self.classes[name]
        for key, value in new_class.__dict__.items():
            if key not in ('__dict__', '__doc__', '__module__', '__weakref__'):
                setattr(cls, key, value)
        return cls
