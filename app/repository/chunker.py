from pathlib import Path
from typing import List


class CodeChunk:

    def __init__(
        self,
        file_path: str,
        start_line: int,
        end_line: int,
        content: str
    ):
        self.file_path = file_path
        self.start_line = start_line
        self.end_line = end_line
        self.content = content

    def to_dict(self):
        return {
            "file_path": self.file_path,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "content": self.content,
        }


class CodeChunker:

    def __init__(self, chunk_size: int = 80):
        self.chunk_size = chunk_size

    def chunk_file(
        self,
        file_path: Path
    ) -> List[CodeChunk]:

        try:
            content = file_path.read_text(
                encoding="utf-8"
            )
        except UnicodeDecodeError:
            return []

        lines = content.splitlines()

        chunks = []

        for start in range(
            0,
            len(lines),
            self.chunk_size
        ):
            end = min(
                start + self.chunk_size,
                len(lines)
            )

            chunk_content = "\n".join(
                lines[start:end]
            )

            if not chunk_content.strip():
                continue

            chunks.append(
                CodeChunk(
                    file_path=str(file_path),
                    start_line=start + 1,
                    end_line=end,
                    content=chunk_content
                )
            )

        return chunks

    def chunk_files(
        self,
        files: List[Path]
    ) -> List[CodeChunk]:

        all_chunks = []

        for file_path in files:
            chunks = self.chunk_file(file_path)
            all_chunks.extend(chunks)

        return all_chunks