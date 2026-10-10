from pathlib import Path

from app.agents.code_generator import GeneratedChange
from app.agents.patch_applier import PatchApplier


def main():

    test_file = Path("test_patch_file.py")

    original_content = """class Example:
    def hello(self):
        return "Hello"
"""

    test_file.write_text(
        original_content,
        encoding="utf-8"
    )

    change = GeneratedChange(
        file_path=str(test_file),

        original_code="""    def hello(self):
        return "Hello"
""",

        new_code="""    def hello(self):
        return "Hello World"
""",

        explanation="Change greeting."
    )

    print("=" * 70)
    print("TESTING PATCH APPLIER")
    print("=" * 70)

    applier = PatchApplier()

    result = applier.apply(change)

    print("\nPatch applied to:")
    print(result)

    print("\nUpdated file:")

    updated_content = test_file.read_text(
        encoding="utf-8"
    )

    print(updated_content)

    # Cleanup test file
    test_file.unlink()

    print("Temporary test file removed.")


if __name__ == "__main__":
    main()