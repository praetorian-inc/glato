def scopeRequired(scope):
    def decorator(func):
        def wrapper(self, *args, **kwargs):
            if not hasattr(self, 'scopes') or scope not in self.scopes:
                print(f'Missing scope: {scope}')
                return None
            return func(self, *args, **kwargs)
        return wrapper
    return decorator
