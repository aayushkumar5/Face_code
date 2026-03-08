"""
FaceCode - Problem Bank
Comprehensive collection of coding problems at different difficulty levels
"""

from enum import Enum
from typing import List, Dict, Optional
from dataclasses import dataclass

class DifficultyLevel(Enum):
    """Problem difficulty levels"""
    EASY = 1
    MEDIUM = 2
    HARD = 3

class HintLevel(Enum):
    """Progressive hint levels"""
    CONCEPTUAL = 1      # High-level approach
    ALGORITHMIC = 2     # Algorithm structure
    IMPLEMENTATION = 3  # Code hints
    SOLUTION = 4        # Near-complete solution

@dataclass
class Hint:
    """Single hint with level"""
    level: HintLevel
    text: str

@dataclass
class TestCase:
    """Test case for problem"""
    input: list
    expected: any
    description: str = ""

@dataclass
class Problem:
    """Coding problem"""
    id: str
    title: str
    description: str
    difficulty: DifficultyLevel
    category: str
    hints: List[Hint]
    test_cases: List[TestCase]
    starter_code: str = ""
    solution: str = ""
    time_limit: int = 300  # 5 minutes default


class ProblemBank:
    """Manages collection of coding problems"""
    
    def __init__(self):
        self.problems = self._initialize_problems()
    
    def get_problem(self, problem_id: str) -> Optional[Problem]:
        """Get problem by ID"""
        return self.problems.get(problem_id)
    
    def get_problems_by_difficulty(self, difficulty: DifficultyLevel) -> List[Problem]:
        """Get all problems of a specific difficulty"""
        return [p for p in self.problems.values() if p.difficulty == difficulty]
    
    def get_random_problem(self, difficulty: DifficultyLevel) -> Problem:
        """Get random problem of specific difficulty"""
        import random
        problems = self.get_problems_by_difficulty(difficulty)
        return random.choice(problems) if problems else None
    
    def _initialize_problems(self) -> Dict[str, Problem]:
        """Initialize all problems"""
        problems = {}
        
        # ===== EASY PROBLEMS =====
        
        problems['E001'] = Problem(
            id='E001',
            title='Sum Two Numbers',
            description="""Write a function that takes two integers and returns their sum.

Example:
  add_numbers(5, 3) → 8
  add_numbers(-2, 7) → 5

Function signature:
  def add_numbers(a: int, b: int) -> int:
      # Your code here
""",
            difficulty=DifficultyLevel.EASY,
            category='basics',
            hints=[
                Hint(HintLevel.CONCEPTUAL, "You need to perform basic arithmetic addition."),
                Hint(HintLevel.ALGORITHMIC, "Use the + operator to add the two numbers."),
                Hint(HintLevel.IMPLEMENTATION, "Simply return a + b"),
            ],
            test_cases=[
                TestCase([5, 3], 8, "Positive numbers"),
                TestCase([-2, 7], 5, "Negative and positive"),
                TestCase([0, 0], 0, "Zero case"),
                TestCase([100, -50], 50, "Large numbers"),
            ],
            starter_code="def add_numbers(a: int, b: int) -> int:\n    pass",
            solution="def add_numbers(a: int, b: int) -> int:\n    return a + b"
        )
        
        problems['E002'] = Problem(
            id='E002',
            title='Check Even Number',
            description="""Write a function that checks if a number is even.

Example:
  is_even(4) → True
  is_even(7) → False

Function signature:
  def is_even(n: int) -> bool:
      # Your code here
""",
            difficulty=DifficultyLevel.EASY,
            category='basics',
            hints=[
                Hint(HintLevel.CONCEPTUAL, "A number is even if it's divisible by 2 with no remainder."),
                Hint(HintLevel.ALGORITHMIC, "Use the modulo operator (%) to check remainder."),
                Hint(HintLevel.IMPLEMENTATION, "Return True if n % 2 == 0, False otherwise."),
            ],
            test_cases=[
                TestCase([4], True, "Even number"),
                TestCase([7], False, "Odd number"),
                TestCase([0], True, "Zero is even"),
                TestCase([-6], True, "Negative even"),
            ],
            starter_code="def is_even(n: int) -> bool:\n    pass",
            solution="def is_even(n: int) -> bool:\n    return n % 2 == 0"
        )
        
        problems['E003'] = Problem(
            id='E003',
            title='Find Maximum',
            description="""Write a function that returns the larger of two numbers.

Example:
  max_of_two(5, 3) → 5
  max_of_two(-1, -5) → -1

Function signature:
  def max_of_two(a: int, b: int) -> int:
      # Your code here
""",
            difficulty=DifficultyLevel.EASY,
            category='basics',
            hints=[
                Hint(HintLevel.CONCEPTUAL, "Compare the two numbers and return the larger one."),
                Hint(HintLevel.ALGORITHMIC, "Use an if-else statement or built-in max()."),
                Hint(HintLevel.IMPLEMENTATION, "if a > b: return a, else: return b"),
            ],
            test_cases=[
                TestCase([5, 3], 5),
                TestCase([-1, -5], -1),
                TestCase([10, 10], 10),
                TestCase([0, -1], 0),
            ],
            starter_code="def max_of_two(a: int, b: int) -> int:\n    pass",
            solution="def max_of_two(a: int, b: int) -> int:\n    return a if a > b else b"
        )
        
        problems['E004'] = Problem(
            id='E004',
            title='String Length',
            description="""Write a function that returns the length of a string WITHOUT using len().

Example:
  string_length("hello") → 5
  string_length("") → 0

Function signature:
  def string_length(s: str) -> int:
      # Your code here
""",
            difficulty=DifficultyLevel.EASY,
            category='strings',
            hints=[
                Hint(HintLevel.CONCEPTUAL, "Count each character in the string."),
                Hint(HintLevel.ALGORITHMIC, "Use a loop to iterate through the string and count."),
                Hint(HintLevel.IMPLEMENTATION, "Initialize count=0, loop through string, increment count, return count."),
            ],
            test_cases=[
                TestCase(["hello"], 5),
                TestCase([""], 0),
                TestCase(["a"], 1),
                TestCase(["Python Programming"], 18),
            ],
            starter_code="def string_length(s: str) -> int:\n    pass",
            solution="def string_length(s: str) -> int:\n    count = 0\n    for char in s:\n        count += 1\n    return count"
        )
        
        problems['E005'] = Problem(
            id='E005',
            title='Reverse String',
            description="""Write a function that reverses a string.

Example:
  reverse_string("hello") → "olleh"
  reverse_string("Python") → "nohtyP"

Function signature:
  def reverse_string(s: str) -> str:
      # Your code here
""",
            difficulty=DifficultyLevel.EASY,
            category='strings',
            hints=[
                Hint(HintLevel.CONCEPTUAL, "Think about accessing string characters in reverse order."),
                Hint(HintLevel.ALGORITHMIC, "Use string slicing with [::-1] or reverse iteration."),
                Hint(HintLevel.IMPLEMENTATION, "return s[::-1]"),
            ],
            test_cases=[
                TestCase(["hello"], "olleh"),
                TestCase(["Python"], "nohtyP"),
                TestCase([""], ""),
                TestCase(["a"], "a"),
            ],
            starter_code="def reverse_string(s: str) -> str:\n    pass",
            solution="def reverse_string(s: str) -> str:\n    return s[::-1]"
        )
        
        # ===== MEDIUM PROBLEMS =====
        
        problems['M001'] = Problem(
            id='M001',
            title='Find Maximum in List',
            description="""Write a function that finds the maximum value in a list.
DO NOT use the built-in max() function.

Example:
  find_max([3, 7, 2, 9, 1]) → 9
  find_max([-5, -1, -10]) → -1

Function signature:
  def find_max(nums: list) -> int:
      # Your code here
""",
            difficulty=DifficultyLevel.MEDIUM,
            category='arrays',
            hints=[
                Hint(HintLevel.CONCEPTUAL, "Keep track of the largest number seen so far as you iterate."),
                Hint(HintLevel.ALGORITHMIC, "Initialize max_val with first element, compare with each subsequent element."),
                Hint(HintLevel.IMPLEMENTATION, "max_val = nums[0]; for num in nums[1:]: if num > max_val: max_val = num"),
            ],
            test_cases=[
                TestCase([[3, 7, 2, 9, 1]], 9),
                TestCase([[-5, -1, -10]], -1),
                TestCase([[42]], 42),
                TestCase([[1, 2, 3, 4, 5]], 5),
            ],
            starter_code="def find_max(nums: list) -> int:\n    pass",
            solution="def find_max(nums: list) -> int:\n    max_val = nums[0]\n    for num in nums[1:]:\n        if num > max_val:\n            max_val = num\n    return max_val"
        )
        
        problems['M002'] = Problem(
            id='M002',
            title='Count Vowels',
            description="""Write a function that counts the number of vowels (a, e, i, o, u) in a string.
Count is case-insensitive.

Example:
  count_vowels("hello") → 2
  count_vowels("AEIOU") → 5
  count_vowels("xyz") → 0

Function signature:
  def count_vowels(s: str) -> int:
      # Your code here
""",
            difficulty=DifficultyLevel.MEDIUM,
            category='strings',
            hints=[
                Hint(HintLevel.CONCEPTUAL, "Check each character to see if it's a vowel."),
                Hint(HintLevel.ALGORITHMIC, "Loop through string, check if lowercase char is in 'aeiou'."),
                Hint(HintLevel.IMPLEMENTATION, "count = 0; for char in s.lower(): if char in 'aeiou': count += 1"),
            ],
            test_cases=[
                TestCase(["hello"], 2),
                TestCase(["AEIOU"], 5),
                TestCase(["xyz"], 0),
                TestCase(["Python Programming"], 4),
            ],
            starter_code="def count_vowels(s: str) -> int:\n    pass",
            solution="def count_vowels(s: str) -> int:\n    count = 0\n    for char in s.lower():\n        if char in 'aeiou':\n            count += 1\n    return count"
        )
        
        problems['M003'] = Problem(
            id='M003',
            title='Palindrome Checker',
            description="""Write a function that checks if a string is a palindrome.
A palindrome reads the same forwards and backwards.
Ignore case and spaces.

Example:
  is_palindrome("racecar") → True
  is_palindrome("hello") → False
  is_palindrome("A man a plan a canal Panama") → True

Function signature:
  def is_palindrome(s: str) -> bool:
      # Your code here
""",
            difficulty=DifficultyLevel.MEDIUM,
            category='strings',
            hints=[
                Hint(HintLevel.CONCEPTUAL, "Compare the string with its reverse, ignoring case and spaces."),
                Hint(HintLevel.ALGORITHMIC, "Clean the string (lowercase, remove spaces), then check if it equals its reverse."),
                Hint(HintLevel.IMPLEMENTATION, "cleaned = s.lower().replace(' ', ''); return cleaned == cleaned[::-1]"),
            ],
            test_cases=[
                TestCase(["racecar"], True),
                TestCase(["hello"], False),
                TestCase(["A man a plan a canal Panama"], True),
                TestCase([""], True),
            ],
            starter_code="def is_palindrome(s: str) -> bool:\n    pass",
            solution="def is_palindrome(s: str) -> bool:\n    cleaned = s.lower().replace(' ', '')\n    return cleaned == cleaned[::-1]"
        )
        
        problems['M004'] = Problem(
            id='M004',
            title='Sum of List',
            description="""Write a function that calculates the sum of all numbers in a list.
DO NOT use the built-in sum() function.

Example:
  sum_list([1, 2, 3, 4, 5]) → 15
  sum_list([-1, 0, 1]) → 0

Function signature:
  def sum_list(nums: list) -> int:
      # Your code here
""",
            difficulty=DifficultyLevel.MEDIUM,
            category='arrays',
            hints=[
                Hint(HintLevel.CONCEPTUAL, "Add up all numbers one by one."),
                Hint(HintLevel.ALGORITHMIC, "Initialize total to 0, loop through list adding each number."),
                Hint(HintLevel.IMPLEMENTATION, "total = 0; for num in nums: total += num; return total"),
            ],
            test_cases=[
                TestCase([[1, 2, 3, 4, 5]], 15),
                TestCase([[-1, 0, 1]], 0),
                TestCase([[10, -5, 3]], 8),
                TestCase([[]], 0),
            ],
            starter_code="def sum_list(nums: list) -> int:\n    pass",
            solution="def sum_list(nums: list) -> int:\n    total = 0\n    for num in nums:\n        total += num\n    return total"
        )
        
        problems['M005'] = Problem(
            id='M005',
            title='Remove Duplicates',
            description="""Write a function that removes duplicate elements from a list,
keeping only the first occurrence of each element.

Example:
  remove_duplicates([1, 2, 2, 3, 1, 4]) → [1, 2, 3, 4]
  remove_duplicates([5, 5, 5]) → [5]

Function signature:
  def remove_duplicates(nums: list) -> list:
      # Your code here
""",
            difficulty=DifficultyLevel.MEDIUM,
            category='arrays',
            hints=[
                Hint(HintLevel.CONCEPTUAL, "Track which elements you've seen and only keep first occurrence."),
                Hint(HintLevel.ALGORITHMIC, "Use a set to track seen elements, build new list with unique items."),
                Hint(HintLevel.IMPLEMENTATION, "seen = set(); result = []; for num in nums: if num not in seen: result.append(num); seen.add(num)"),
            ],
            test_cases=[
                TestCase([[1, 2, 2, 3, 1, 4]], [1, 2, 3, 4]),
                TestCase([[5, 5, 5]], [5]),
                TestCase([[1, 2, 3]], [1, 2, 3]),
                TestCase([[]], []),
            ],
            starter_code="def remove_duplicates(nums: list) -> list:\n    pass",
            solution="def remove_duplicates(nums: list) -> list:\n    seen = set()\n    result = []\n    for num in nums:\n        if num not in seen:\n            result.append(num)\n            seen.add(num)\n    return result"
        )
        
        # ===== HARD PROBLEMS =====
        
        problems['H001'] = Problem(
            id='H001',
            title='Two Sum',
            description="""Given a list of integers and a target sum, return indices of two numbers
that add up to the target. You may assume exactly one solution exists.

Example:
  two_sum([2, 7, 11, 15], 9) → [0, 1]  # Because 2 + 7 = 9
  two_sum([3, 2, 4], 6) → [1, 2]       # Because 2 + 4 = 6

Function signature:
  def two_sum(nums: list, target: int) -> list:
      # Your code here
""",
            difficulty=DifficultyLevel.HARD,
            category='arrays',
            hints=[
                Hint(HintLevel.CONCEPTUAL, "For each number, check if its complement (target - num) exists in the list."),
                Hint(HintLevel.ALGORITHMIC, "Use a dictionary to store numbers and their indices for O(1) lookup."),
                Hint(HintLevel.IMPLEMENTATION, "seen = {}; for i, num in enumerate(nums): complement = target - num; if complement in seen: return [seen[complement], i]; seen[num] = i"),
            ],
            test_cases=[
                TestCase([[2, 7, 11, 15], 9], [0, 1]),
                TestCase([[3, 2, 4], 6], [1, 2]),
                TestCase([[3, 3], 6], [0, 1]),
                TestCase([[1, 5, 3, 7], 10], [1, 3]),
            ],
            starter_code="def two_sum(nums: list, target: int) -> list:\n    pass",
            solution="def two_sum(nums: list, target: int) -> list:\n    seen = {}\n    for i, num in enumerate(nums):\n        complement = target - num\n        if complement in seen:\n            return [seen[complement], i]\n        seen[num] = i\n    return []"
        )
        
        problems['H002'] = Problem(
            id='H002',
            title='Fibonacci Sequence',
            description="""Write a function that returns the nth Fibonacci number.
The Fibonacci sequence: 0, 1, 1, 2, 3, 5, 8, 13, 21...
(Each number is the sum of the previous two)

Example:
  fibonacci(0) → 0
  fibonacci(1) → 1
  fibonacci(6) → 8
  fibonacci(10) → 55

Function signature:
  def fibonacci(n: int) -> int:
      # Your code here
""",
            difficulty=DifficultyLevel.HARD,
            category='recursion',
            hints=[
                Hint(HintLevel.CONCEPTUAL, "Build up from base cases (fib(0)=0, fib(1)=1), each new number is sum of previous two."),
                Hint(HintLevel.ALGORITHMIC, "Use iteration with two variables tracking the last two numbers."),
                Hint(HintLevel.IMPLEMENTATION, "if n <= 1: return n; a, b = 0, 1; for _ in range(2, n+1): a, b = b, a+b; return b"),
            ],
            test_cases=[
                TestCase([0], 0),
                TestCase([1], 1),
                TestCase([6], 8),
                TestCase([10], 55),
            ],
            starter_code="def fibonacci(n: int) -> int:\n    pass",
            solution="def fibonacci(n: int) -> int:\n    if n <= 1:\n        return n\n    a, b = 0, 1\n    for _ in range(2, n + 1):\n        a, b = b, a + b\n    return b",
            time_limit=600  # 10 minutes for harder problem
        )
        
        problems['H003'] = Problem(
            id='H003',
            title='Valid Parentheses',
            description="""Write a function that checks if a string of parentheses is valid.
Valid means every opening bracket has a matching closing bracket in the correct order.

Example:
  valid_parentheses("()") → True
  valid_parentheses("()[]{}") → True
  valid_parentheses("(]") → False
  valid_parentheses("([)]") → False
  valid_parentheses("{[]}") → True

Function signature:
  def valid_parentheses(s: str) -> bool:
      # Your code here
""",
            difficulty=DifficultyLevel.HARD,
            category='stacks',
            hints=[
                Hint(HintLevel.CONCEPTUAL, "Use a stack data structure to track opening brackets."),
                Hint(HintLevel.ALGORITHMIC, "Push opening brackets onto stack. When you see closing bracket, check if it matches top of stack."),
                Hint(HintLevel.IMPLEMENTATION, "stack = []; pairs = {')': '(', ']': '[', '}': '{'}; for char in s: if char in '([{': stack.append(char); elif not stack or stack.pop() != pairs[char]: return False; return len(stack) == 0"),
            ],
            test_cases=[
                TestCase(["()"], True),
                TestCase(["()[]{}"], True),
                TestCase(["(]"], False),
                TestCase(["([)]"], False),
                TestCase(["{[]}"], True),
            ],
            starter_code="def valid_parentheses(s: str) -> bool:\n    pass",
            solution="def valid_parentheses(s: str) -> bool:\n    stack = []\n    pairs = {')': '(', ']': '[', '}': '{'}\n    for char in s:\n        if char in '([{':\n            stack.append(char)\n        elif char in ')]}':\n            if not stack or stack.pop() != pairs[char]:\n                return False\n    return len(stack) == 0",
            time_limit=600
        )
        
        return problems


# Test the problem bank
if __name__ == "__main__":
    bank = ProblemBank()
    
    print("=" * 60)
    print("PROBLEM BANK TEST")
    print("=" * 60)
    
    # Count problems by difficulty
    for difficulty in DifficultyLevel:
        problems = bank.get_problems_by_difficulty(difficulty)
        print(f"\n{difficulty.name}: {len(problems)} problems")
        for p in problems:
            print(f"  - {p.id}: {p.title} ({p.category})")
            print(f"    Hints: {len(p.hints)}, Test Cases: {len(p.test_cases)}")
    
    # Test a specific problem
    print("\n" + "=" * 60)
    print("SAMPLE PROBLEM: Two Sum")
    print("=" * 60)
    
    problem = bank.get_problem('H001')
    print(f"\nTitle: {problem.title}")
    print(f"Difficulty: {problem.difficulty.name}")
    print(f"Category: {problem.category}")
    print(f"\nDescription:\n{problem.description}")
    print(f"\nHints:")
    for i, hint in enumerate(problem.hints):
        print(f"  {i+1}. [{hint.level.name}] {hint.text}")
    print(f"\nTest Cases:")
    for i, test in enumerate(problem.test_cases):
        print(f"  {i+1}. Input: {test.input} → Expected: {test.expected}")
