"""Indented C writer, Allman style."""


class Out:
    def __init__(self):
        self.lines = []
        self.level = 0

    def line(self, text=""):
        self.lines.append(("    " * self.level + text) if text else "")

    def open(self, head):
        self.line(head)
        self.line("{")
        self.level += 1

    def close(self, tail=""):
        self.level -= 1
        self.line("}" + tail)

    def text(self):
        return "\n".join(self.lines) + "\n"
