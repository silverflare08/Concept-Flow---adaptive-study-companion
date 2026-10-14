"""Request-local routing to account-specific study state, including worker jobs."""
from contextvars import ContextVar, copy_context

account_context = ContextVar("account_context", default=None)


class AccountProxy:
    def __init__(self, key, default):
        object.__setattr__(self, "key", key)
        object.__setattr__(self, "default", default)

    def target(self):
        context = account_context.get()
        return context[self.key] if context is not None else self.default

    def __getattr__(self, name):
        return getattr(self.target(), name)

    def __setattr__(self, name, value):
        setattr(self.target(), name, value)

    def __truediv__(self, value):
        return self.target() / value


def submit_account_job(executor, function, *args):
    return executor.submit(copy_context().run, function, *args)
