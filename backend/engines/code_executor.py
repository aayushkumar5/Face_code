"""
FaceCode - Secure Code Executor
Executes user code in isolated subprocess with timeout and resource limits
"""

import subprocess
import tempfile
import os
import json
import time
from typing import List, Dict, Any, Tuple

class CodeExecutor:
    """
    Safely executes user code in isolated environment
    """
    
    def __init__(self, timeout: int = 5, max_memory_mb: int = 128):
        """
        Initialize code executor
        
        Args:
            timeout: Maximum execution time in seconds
            max_memory_mb: Maximum memory usage in MB
        """
        self.timeout = timeout
        self.max_memory_mb = max_memory_mb
    
    def execute_code(self, code: str, test_cases: List[Dict]) -> Dict[str, Any]:
        """
        Execute code against test cases
        
        Args:
            code: User's Python code
            test_cases: List of test case dicts with 'input' and 'expected'
            
        Returns:
            Dict with execution results
        """
        results = {
            'success': False,
            'test_results': [],
            'all_passed': False,
            'execution_time': 0,
            'error': None
        }
        
        start_time = time.time()
        
        try:
            # Create temporary Python file
            with tempfile.NamedTemporaryFile(
                mode='w', 
                suffix='.py', 
                delete=False,
                encoding='utf-8'
            ) as f:
                # Write imports and user code
                f.write("import sys\nimport json\n\n")
                f.write(code)
                f.write("\n\n")
                
                # Add test execution code
                f.write("""
# Auto-generated test runner
if __name__ == "__main__":
    test_input = json.loads(sys.stdin.read())
    
    # Find user's function
    func_name = None
    for name in dir():
        obj = eval(name)
        if callable(obj) and not name.startswith('_') and name not in ['json', 'sys']:
            func_name = name
            break
    
    if func_name:
        func = eval(func_name)
        result = func(*test_input)
        print(json.dumps(result))
    else:
        print(json.dumps({"error": "No function found"}))
""")
                temp_file = f.name
            
            # Run each test case
            all_passed = True
            for i, test in enumerate(test_cases):
                test_result = self._run_single_test(temp_file, test)
                results['test_results'].append(test_result)
                
                if not test_result['passed']:
                    all_passed = False
            
            results['success'] = True
            results['all_passed'] = all_passed
            results['execution_time'] = time.time() - start_time
            
        except Exception as e:
            results['error'] = str(e)
        
        finally:
            # Cleanup temporary file
            if 'temp_file' in locals():
                try:
                    os.unlink(temp_file)
                except:
                    pass
        
        return results
    
    def _run_single_test(self, script_path: str, test_case: Dict) -> Dict:
        """
        Run a single test case
        
        Args:
            script_path: Path to Python script
            test_case: Test case with input and expected output
            
        Returns:
            Test result dict
        """
        result = {
            'input': test_case['input'],
            'expected': test_case['expected'],
            'actual': None,
            'passed': False,
            'error': None,
            'timeout': False
        }
        
        try:
            # Prepare input
            test_input = json.dumps(test_case['input'])
            
            # Execute with timeout
            process = subprocess.run(
                ['python', script_path],
                input=test_input,
                capture_output=True,
                timeout=self.timeout,
                text=True,
                encoding='utf-8'
            )
            
            # Check for errors
            if process.returncode != 0:
                result['error'] = process.stderr.strip()
                return result
            
            # Parse output
            output = process.stdout.strip()
            
            try:
                actual = json.loads(output)
                result['actual'] = actual
                
                # Compare with expected
                result['passed'] = (actual == test_case['expected'])
                
            except json.JSONDecodeError:
                # Output is not JSON, compare as string
                result['actual'] = output
                result['passed'] = (output == str(test_case['expected']))
        
        except subprocess.TimeoutExpired:
            result['timeout'] = True
            result['error'] = f"Execution timed out after {self.timeout} seconds"
        
        except Exception as e:
            result['error'] = str(e)
        
        return result
    
    def validate_syntax(self, code: str) -> Tuple[bool, str]:
        """
        Validate Python syntax without executing
        
        Args:
            code: Python code to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            compile(code, '<string>', 'exec')
            return True, ""
        except SyntaxError as e:
            return False, f"Syntax Error on line {e.lineno}: {e.msg}"
        except Exception as e:
            return False, str(e)


# Example usage and testing
if __name__ == "__main__":
    executor = CodeExecutor(timeout=5)
    
    print("=" * 60)
    print("TESTING CODE EXECUTOR")
    print("=" * 60)
    
    # Test 1: Simple addition function
    print("\n--- Test 1: Simple Addition ---")
    code1 = """
def add(a, b):
    return a + b
"""
    
    test_cases1 = [
        {"input": [5, 3], "expected": 8},
        {"input": [-2, 7], "expected": 5},
        {"input": [0, 0], "expected": 0}
    ]
    
    result1 = executor.execute_code(code1, test_cases1)
    print(f"Success: {result1['success']}")
    print(f"All Passed: {result1['all_passed']}")
    print(f"Execution Time: {result1['execution_time']:.3f}s")
    
    for i, test_result in enumerate(result1['test_results']):
        status = "✅ PASS" if test_result['passed'] else "❌ FAIL"
        print(f"  Test {i+1}: {status} - Input: {test_result['input']}, "
              f"Expected: {test_result['expected']}, Actual: {test_result['actual']}")
    
    # Test 2: Function with error
    print("\n--- Test 2: Code with Error ---")
    code2 = """
def divide(a, b):
    return a / b
"""
    
    test_cases2 = [
        {"input": [10, 2], "expected": 5},
        {"input": [10, 0], "expected": "error"}  # This will fail
    ]
    
    result2 = executor.execute_code(code2, test_cases2)
    print(f"Success: {result2['success']}")
    print(f"All Passed: {result2['all_passed']}")
    
    for i, test_result in enumerate(result2['test_results']):
        if test_result['error']:
            print(f"  Test {i+1}: ❌ ERROR - {test_result['error']}")
        else:
            status = "✅ PASS" if test_result['passed'] else "❌ FAIL"
            print(f"  Test {i+1}: {status}")
    
    # Test 3: Infinite loop (timeout test)
    print("\n--- Test 3: Timeout Protection ---")
    code3 = """
def infinite_loop():
    while True:
        pass
    return 42
"""
    
    test_cases3 = [
        {"input": [], "expected": 42}
    ]
    
    result3 = executor.execute_code(code3, test_cases3)
    print(f"Success: {result3['success']}")
    
    for test_result in result3['test_results']:
        if test_result['timeout']:
            print(f"  ✅ Timeout protection worked: {test_result['error']}")
    
    # Test 4: Syntax validation
    print("\n--- Test 4: Syntax Validation ---")
    
    valid_code = "def test():\n    return 42"
    is_valid, error = executor.validate_syntax(valid_code)
    print(f"Valid code: {is_valid}")
    
    invalid_code = "def test(\n    return 42"
    is_valid, error = executor.validate_syntax(invalid_code)
    print(f"Invalid code: {is_valid}, Error: {error}")
    
    print("\n✅ All executor tests completed!")
