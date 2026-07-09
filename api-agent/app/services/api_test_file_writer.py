from __future__ import annotations

from app.schemas.generated_file import GeneratedFile
from app.schemas.llm_outputs import TestCodeOutput
from app.tools.file_writer_tool import FileWriterTool


class ApiTestFileWriter:
    def __init__(self) -> None:
        self.writer = FileWriterTool()

    def write(self, repo_path: str, output: TestCodeOutput) -> list[GeneratedFile]:
        generated: list[GeneratedFile] = []
        for file in output.files:
            generated.append(
                self.writer.write_text(
                    repo_path=repo_path,
                    relative_path=file.relative_path,
                    content=file.content,
                    test_target=file.test_target,
                    summary=file.summary,
                )
            )
        return generated
