"""
core/exercise_registry.py — Auto-discovers and loads exercise modules

Auto-discovery process:
  1. Scan exercises/ folder for .py files
  2. Load each module
  3. Look for EXERCISE_KEY constant and WorkoutController class
  4. Register if both found

Developers add new exercises by:
  1. Copy exercises/_template.py → exercises/leg_exercise.py
  2. Set EXERCISE_KEY = "leg"
  3. Implement the exercise logic
  4. No other registration needed — registry auto-discovers on startup
"""
import importlib
import pkgutil
import exercises


class ExerciseRegistry:
    """Registry of loaded exercises."""

    def __init__(self):
        """Initialize and auto-discover all exercises."""
        self._controllers = {}
        self._load_all()

    def _load_all(self):
        """Scan exercises/ folder and load all valid modules."""
        for _, name, _ in pkgutil.iter_modules(exercises.__path__):
            # Skip private modules
            if name.startswith("_"):
                continue

            try:
                mod = importlib.import_module(f"exercises.{name}")

                # Look for EXERCISE_KEY and WorkoutController
                key = getattr(mod, "EXERCISE_KEY", None)
                cls = getattr(mod, "WorkoutController", None)

                if key and cls:
                    self._controllers[key] = cls()
                    print(f"✓ Loaded: '{key}' ← {name}.py")

            except Exception as e:
                print(f"✗ Error loading {name}: {e}")

    def get(self, key: str):
        """
        Get exercise controller by key.

        Args:
            key: exercise key (e.g., "hand", "leg")

        Returns:
            WorkoutController instance, or None if not found
        """
        return self._controllers.get(key)

    def keys(self):
        """Get list of loaded exercise keys."""
        return list(self._controllers.keys())