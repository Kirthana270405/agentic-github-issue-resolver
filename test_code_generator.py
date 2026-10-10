from app.agents.code_generator import CodeGeneratorAgent


def main():

    generator = CodeGeneratorAgent()

    print("=" * 70)
    print("TESTING CODE GENERATOR")
    print("=" * 70)

    change = generator.generate(
        problem="The Session class needs to store cookies between requests.",

        expected_behavior="Cookies should persist across requests made by the same Session.",

        file_path="src/requests/sessions.py",

        planned_change="Add a cookie storage field to the Session class.",

        reason="The Session needs persistent cookie storage.",

        file_content="""class Session:
    def __init__(self):
        self.headers = {}
        self.auth = None

    def request(self, method, url, **kwargs):
        return self.send(method, url, **kwargs)
"""
    )

    print("\n" + "=" * 70)
    print("GENERATED CHANGE")
    print("=" * 70)

    print("\nFile:")
    print(change.file_path)

    print("\nOriginal Code:")
    print(change.original_code)

    print("\nNew Code:")
    print(change.new_code)

    print("\nExplanation:")
    print(change.explanation)


if __name__ == "__main__":
    main()