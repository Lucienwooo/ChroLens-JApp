import ast
import sys

def analyze(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        tree = ast.parse(f.read())
    
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            print(f"Function: {node.name} at line {node.lineno}")
        elif isinstance(node, ast.ClassDef):
            print(f"Class: {node.name} at line {node.lineno}")

if __name__ == '__main__':
    analyze(sys.argv[1])
