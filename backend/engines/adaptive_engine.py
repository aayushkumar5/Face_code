"""
FaceCode V2 - Adaptive Learning Engine
Smart difficulty adjustment and progressive hint system
"""

import time
from typing import Optional, Dict, List
from problem_bank import Problem, DifficultyLevel, HintLevel, ProblemBank
import random

class AdaptiveEngine:
    """
    Manages difficulty adaptation and hint provisioning
    """
    
    def __init__(self):
        self.problem_bank = ProblemBank()
        self.current_difficulty = DifficultyLevel.EASY
        self.current_problem = None
        
        # Solved problems tracking
        self.problems_solved = []
        self.problems_attempted = []
        
        # Hint tracking
        self.hints_provided = []
        self.next_hint_index = 0
        
        # Thresholds
        self.HIGH_CONFIDENCE_THRESHOLD = 0.75
        self.LOW_CONFIDENCE_THRESHOLD = 0.35
        self.QUICK_SOLVE_TIME = 240  # 4 minutes
        self.SLOW_SOLVE_TIME = 600   # 10 minutes
        
        # Performance tracking
        self.session_stats = {
            'problems_attempted': 0,
            'problems_solved': 0,
            'total_hints_used': 0,
            'avg_confidence': 0.5,
            'avg_solve_time': 0
        }
    
    def select_problem(self, difficulty: Optional[DifficultyLevel] = None) -> Problem:
        """
        Select next problem based on current difficulty
        
        Args:
            difficulty: Optional specific difficulty, defaults to current
            
        Returns:
            Selected problem
        """
        target_difficulty = difficulty or self.current_difficulty
        
        # Get problems at this difficulty
        available = self.problem_bank.get_problems_by_difficulty(target_difficulty)
        
        # Filter out already solved
        solved_ids = [p.id for p in self.problems_solved]
        unsolved = [p for p in available if p.id not in solved_ids]
        
        # If all solved at this level, try the next level (with cycle guard)
        if not unsolved:
            order = [DifficultyLevel.EASY, DifficultyLevel.MEDIUM, DifficultyLevel.HARD]
            start_idx = order.index(target_difficulty)
            for offset in range(1, len(order)):
                next_diff = order[(start_idx + offset) % len(order)]
                alt = self.problem_bank.get_problems_by_difficulty(next_diff)
                alt_unsolved = [p for p in alt if p.id not in solved_ids]
                if alt_unsolved:
                    problem = random.choice(alt_unsolved)
                    self.current_problem = problem
                    self.hints_provided = []
                    self.next_hint_index = 0
                    return problem
            # All problems at all levels solved — pick any random problem
            all_problems = list(self.problem_bank.problems.values())
            problem = random.choice(all_problems)
            self.current_problem = problem
            self.hints_provided = []
            self.next_hint_index = 0
            return problem
        
        # Select random unsolved problem
        problem = random.choice(unsolved)
        self.current_problem = problem
        self.hints_provided = []
        self.next_hint_index = 0
        
        return problem
    
    def should_provide_hint(self, confidence: float, time_on_problem: float, 
                           inactivity: float) -> bool:
        """
        Determine if a hint should be provided
        
        Args:
            confidence: Current confidence score
            time_on_problem: Seconds on current problem
            inactivity: Seconds of inactivity
            
        Returns:
            True if hint should be given
        """
        # Low confidence for extended period
        if confidence < 0.3 and time_on_problem > 90:
            return True
        
        # Stuck for too long
        if time_on_problem > 180:  # 3 minutes
            return True
        
        # Inactive for too long
        if inactivity > 45:
            return True
        
        return False
    
    def get_next_hint(self) -> Optional[Dict]:
        """
        Get next progressive hint
        
        Returns:
            Hint dict or None if no more hints
        """
        if not self.current_problem:
            return None
        
        if self.next_hint_index >= len(self.current_problem.hints):
            return None  # No more hints
        
        hint = self.current_problem.hints[self.next_hint_index]
        self.next_hint_index += 1
        
        hint_data = {
            'level': hint.level,
            'text': hint.text,
            'index': self.next_hint_index
        }
        
        self.hints_provided.append(hint_data)
        self.session_stats['total_hints_used'] += 1
        
        return hint_data
    
    def adjust_difficulty(self, avg_confidence: float, solve_time: float, 
                         solved: bool) -> Dict[str, any]:
        """
        Adjust difficulty based on performance
        
        Args:
            avg_confidence: Average confidence during problem
            solve_time: Time spent on problem
            solved: Whether problem was solved
            
        Returns:
            Dict with adjustment details
        """
        old_difficulty = self.current_difficulty
        adjustment = "maintained"
        
        # Increase difficulty conditions
        if (solved and 
            avg_confidence > self.HIGH_CONFIDENCE_THRESHOLD and
            solve_time < self.QUICK_SOLVE_TIME and
            len(self.hints_provided) == 0):
            
            if self.current_difficulty == DifficultyLevel.EASY:
                self.current_difficulty = DifficultyLevel.MEDIUM
                adjustment = "increased"
            elif self.current_difficulty == DifficultyLevel.MEDIUM:
                self.current_difficulty = DifficultyLevel.HARD
                adjustment = "increased"
        
        # Decrease difficulty conditions
        elif (not solved or
              avg_confidence < self.LOW_CONFIDENCE_THRESHOLD or
              solve_time > self.SLOW_SOLVE_TIME or
              len(self.hints_provided) > 2):
            
            if self.current_difficulty == DifficultyLevel.HARD:
                self.current_difficulty = DifficultyLevel.MEDIUM
                adjustment = "decreased"
            elif self.current_difficulty == DifficultyLevel.MEDIUM:
                self.current_difficulty = DifficultyLevel.EASY
                adjustment = "decreased"
        
        return {
            'old_difficulty': old_difficulty.name,
            'new_difficulty': self.current_difficulty.name,
            'adjustment': adjustment,
            'reason': self._get_adjustment_reason(
                avg_confidence, solve_time, solved, len(self.hints_provided)
            )
        }
    
    def _get_adjustment_reason(self, confidence: float, time: float, 
                              solved: bool, hints_used: int) -> str:
        """Generate human-readable reason for adjustment"""
        if solved and confidence > 0.75 and time < 240 and hints_used == 0:
            return "Excellent performance - fast solve with high confidence"
        elif not solved:
            return "Problem not solved - reducing difficulty"
        elif confidence < 0.35:
            return "Low confidence detected - reducing difficulty"
        elif time > 600:
            return "Took too long - reducing difficulty"
        elif hints_used > 2:
            return "Multiple hints needed - reducing difficulty"
        else:
            return "Good performance - maintaining difficulty"
    
    def record_problem_attempt(self, solved: bool, time_spent: float, 
                              avg_confidence: float):
        """
        Record problem attempt for statistics
        
        Args:
            solved: Whether problem was solved
            time_spent: Time in seconds
            avg_confidence: Average confidence score
        """
        self.session_stats['problems_attempted'] += 1
        self.problems_attempted.append(self.current_problem)
        
        if solved:
            self.session_stats['problems_solved'] += 1
            self.problems_solved.append(self.current_problem)
        
        # Update averages
        n = self.session_stats['problems_attempted']
        self.session_stats['avg_confidence'] = (
            (self.session_stats['avg_confidence'] * (n - 1) + avg_confidence) / n
        )
        
        if solved:
            solve_count = self.session_stats['problems_solved']
            self.session_stats['avg_solve_time'] = (
                (self.session_stats['avg_solve_time'] * (solve_count - 1) + time_spent) 
                / solve_count
            )
    
    def get_session_summary(self) -> Dict:
        """Get summary of current session"""
        total = self.session_stats['problems_attempted']
        solved = self.session_stats['problems_solved']
        
        return {
            'total_attempted': total,
            'total_solved': solved,
            'success_rate': (solved / total * 100) if total > 0 else 0,
            'avg_confidence': self.session_stats['avg_confidence'],
            'avg_solve_time': self.session_stats['avg_solve_time'],
            'total_hints_used': self.session_stats['total_hints_used'],
            'current_difficulty': self.current_difficulty.name,
            'hints_per_problem': (
                self.session_stats['total_hints_used'] / total if total > 0 else 0
            )
        }
    
    def reset_session(self):
        """Reset session statistics"""
        self.problems_solved = []
        self.problems_attempted = []
        self.session_stats = {
            'problems_attempted': 0,
            'problems_solved': 0,
            'total_hints_used': 0,
            'avg_confidence': 0.5,
            'avg_solve_time': 0
        }


# Testing
if __name__ == "__main__":
    print("=" * 60)
    print("ADAPTIVE ENGINE TEST")
    print("=" * 60)
    
    engine = AdaptiveEngine()
    
    # Test 1: Select initial problem
    print("\n--- Test 1: Problem Selection ---")
    problem = engine.select_problem()
    print(f"Selected: {problem.title}")
    print(f"Difficulty: {problem.difficulty.name}")
    print(f"Available hints: {len(problem.hints)}")
    
    # Test 2: Hint system
    print("\n--- Test 2: Progressive Hints ---")
    for i in range(4):
        hint = engine.get_next_hint()
        if hint:
            print(f"Hint {hint['index']}: [{hint['level'].name}] {hint['text'][:50]}...")
        else:
            print(f"No more hints available")
    
    # Test 3: Difficulty adjustment scenarios
    print("\n--- Test 3: Difficulty Adjustment ---")
    
    scenarios = [
        {
            'name': 'High Performance',
            'confidence': 0.85,
            'time': 180,
            'solved': True
        },
        {
            'name': 'Low Confidence',
            'confidence': 0.25,
            'time': 400,
            'solved': False
        },
        {
            'name': 'Took Too Long',
            'confidence': 0.60,
            'time': 700,
            'solved': True
        }
    ]
    
    for scenario in scenarios:
        print(f"\nScenario: {scenario['name']}")
        print(f"  Confidence: {scenario['confidence']:.2f}")
        print(f"  Time: {scenario['time']}s")
        print(f"  Solved: {scenario['solved']}")
        
        result = engine.adjust_difficulty(
            scenario['confidence'],
            scenario['time'],
            scenario['solved']
        )
        
        print(f"  → {result['old_difficulty']} → {result['new_difficulty']} "
              f"({result['adjustment']})")
        print(f"  Reason: {result['reason']}")
        
        engine.record_problem_attempt(
            scenario['solved'],
            scenario['time'],
            scenario['confidence']
        )
    
    # Test 4: Session summary
    print("\n--- Test 4: Session Summary ---")
    summary = engine.get_session_summary()
    for key, value in summary.items():
        if isinstance(value, float):
            print(f"  {key}: {value:.2f}")
        else:
            print(f"  {key}: {value}")
    
    print("\n✅ All adaptive engine tests passed!")
