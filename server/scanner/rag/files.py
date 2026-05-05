import os
import glob

SUPPORTED_EXTENSIONS = ["py", "js", "java", "c", "cpp", "go", "php", "rb", "ts", "jsx", "tsx", "html", "css", "cs", "kt", "kts", "scala", 
                        "h", "cc", "cxx", "hpp", "hh", "hxx", "htm", "sql", "swift", "rs", "sh", "m", "dart", "r", "pl", "pm", "xml", "yaml", "yml" ]

def get_source_files(folder_path):
    """Recursively collect source code files from the folder."""
    files = []
    for ext in SUPPORTED_EXTENSIONS:
        pattern = os.path.join(folder_path, f"**/*.{ext}")
        files.extend(glob.glob(pattern, recursive=True))
    return files

def read_file(file_path):
    """Read content of a file, return as string."""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()
    except Exception as e:
        return ""

def chunk_code(code, max_lines=80):
    """Split long files into chunks of N lines."""
    lines = code.splitlines()
    return ["\n".join(lines[i:i + max_lines]) for i in range(0, len(lines), max_lines)]
