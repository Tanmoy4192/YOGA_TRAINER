"""core/exercise_registry.py — auto-discovers exercises/ folder"""
import importlib
import pkgutil
import exercises


class ExerciseRegistry:
    def __init__(self):
        self._controllers = {}
        self._load_all()

    def _load_all(self):
        for _, name, _ in pkgutil.iter_modules(exercises.__path__):
            if name.startswith("_"):
                continue
            try:
                mod = importlib.import_module(f"exercises.{name}")
                key = getattr(mod, "EXERCISE_KEY", None)
                cls = getattr(mod, "WorkoutController", None)
                if key and cls:
                    self._controllers[key] = cls()
                    print(f"[Registry] Loaded: '{key}' ← {name}.py")
            except Exception as e:
                print(f"[Registry] ERROR loading {name}: {e}")

    def get(self, key: str):
        return self._controllers.get(key)

    def keys(self):
        return list(self._controllers.keys())