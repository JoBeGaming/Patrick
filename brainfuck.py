import collections.abc


__all__ = [
    "BRAINFUCK_MEMORY_LIMIT",
    "process_brainfuck",
]


BRAINFUCK_LOOP_LIMIT: int = 1000
BRAINFUCK_MEMORY_LIMIT: int = 30000



class Memory:
    def __init__(self, input: str) -> None:
        self.counter: int = 0
        self.pointer: int = 0
        self.cells: collections.abc.MutableSequence[int] = [0] * BRAINFUCK_MEMORY_LIMIT
        self.input: str = input
        self.input_index: int = 0
        self.output: str = ""
        self.loops_counter: int = 0
        self.brace_map: collections.abc.MutableMapping[int, int] = {}


def create_brace_map(code: str) -> collections.abc.MutableMapping[int, int]:
    """
    Create a mapping of opening to closing brace indicies for jumping / branching.
    """

    brace_map: collections.abc.MutableMapping[int, int] = {}
    stack: collections.deque[int] = collections.deque()
    ptr: int = 0

    while ptr < len(code):
        if code[ptr] == "[":
            stack.append(ptr)
        elif code[ptr] == "]":
            if not stack:
                raise SyntaxError("Unmatched ']'")
            opening_brace = stack.pop()
            brace_map[opening_brace] = ptr
            brace_map[ptr] = opening_brace

        ptr += 1

    if stack:
        # Remaining '[' exist.
        raise SyntaxError(stack.pop())

    return brace_map


def process_brainfuck(code: str, input: str) -> str:
    memory = Memory(input)
    try:
        memory.brace_map = create_brace_map(code)
    except SyntaxError as e:
        return f"error: unmatched '[' at character {e.args[0]}"

    while memory.counter < len(code):
        match code[memory.counter]:
            case ">":
                if memory.pointer < BRAINFUCK_MEMORY_LIMIT - 1:
                    memory.pointer += 1
                else:
                    return f"error: pointer moved above {BRAINFUCK_MEMORY_LIMIT - 1} at character {memory.counter}"

            case "<":
                if memory.pointer > 0:
                    memory.pointer -= 1
                else:
                    return f"error: pointer moved below 0 at character {memory.counter}"

            case "+":
                memory.cells[memory.pointer] = (memory.cells[memory.pointer] + 1) % 256

            case "-":
                memory.cells[memory.pointer] = (memory.cells[memory.pointer] - 1) % 256

            case ".":
                memory.output += chr(memory.cells[memory.pointer])

            case ",":
                if memory.input_index < len(memory.input):
                    memory.cells[memory.pointer] = ord(memory.input[memory.input_index])
                    memory.input_index += 1
                else:
                    return f"error: input exhausted at character {memory.counter}"

            case "[":
                if memory.cells[memory.pointer] == 0:
                    memory.counter = memory.brace_map[memory.counter]

            case "]":
                if memory.cells[memory.pointer] != 0:
                    memory.counter = memory.brace_map[memory.counter]
                    memory.loops_counter += 1
                    if memory.loops_counter > BRAINFUCK_LOOP_LIMIT:
                        return f"error: infinite loop detected at character {memory.counter}"
                else:
                    memory.loops_counter = 0

            # All non-brainfuck characters get skipped.
            case _:
                pass

        memory.counter += 1

    return memory.output
