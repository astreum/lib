class AstreumMachine:
    def __init__(self):
        pass

    def evaluate(self, code: str) -> list[str]:
        return self.tokenize(code)

    def tokenize(self, input: str) -> list[str]:
        tokens = input.replace("(", " ( ").replace(")", " ) ").split()
        return tokens
