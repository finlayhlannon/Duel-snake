import typing
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Set, Tuple, Optional

class Direction(Enum):
    UP = "up"
    DOWN = "down"
    LEFT = "left"
    RIGHT = "right"

@dataclass
class Position:
    x: int
    y: int

    def __hash__(self):
        return hash((self.x, self.y))

    def to_dict(self) -> Dict:
        return {"x": self.x, "y": self.y}

class MovementStrategy:
    def __init__(self, game_state: Dict):
        self.game_state = game_state
        self.board_width = game_state['board']['width']
        self.board_height = game_state['board']['height']
        self.my_snake = game_state['you']
        self.my_head = Position(game_state['you']['body'][0]['x'], game_state['you']['body'][0]['y'])
        self.my_length = len(game_state['you']['body'])
        self.health = game_state['you']['health']
        self.opponents = [snake for snake in game_state['board']['snakes'] if snake['id'] != game_state['you']['id']]

    def get_safe_moves(self) -> Dict[Direction, float]:
        """Calculate base safety scores for each possible move."""
        moves = {
            Direction.UP: 0,
            Direction.DOWN: 0,
            Direction.LEFT: 0,
            Direction.RIGHT: 0
        }

        # Check basic collision avoidance
        for direction in moves:
            next_pos = self._get_next_position(direction)
            if self._is_valid_position(next_pos):
                moves[direction] = self._calculate_position_safety(next_pos)
            else:
                moves[direction] = float('-inf')

        return moves

    def _get_next_position(self, direction: Direction) -> Position:
        """Get the next position for a given direction."""
        if direction == Direction.UP:
            return Position(self.my_head.x, self.my_head.y + 1)
        elif direction == Direction.DOWN:
            return Position(self.my_head.x, self.my_head.y - 1)
        elif direction == Direction.LEFT:
            return Position(self.my_head.x - 1, self.my_head.y)
        else:  # RIGHT
            return Position(self.my_head.x + 1, self.my_head.y)

    def _is_valid_position(self, pos: Position) -> bool:
        """Check if a position is within board boundaries."""
        return 0 <= pos.x < self.board_width and 0 <= pos.y < self.board_height

    def _calculate_position_safety(self, pos: Position) -> float:
        """Calculate safety score for a position."""
        safety_score = 100.0

        # Check for immediate collisions with snake bodies
        for snake in self.game_state['board']['snakes']:
            for segment in snake['body'][:-1]:  # Exclude tail
                if pos.x == segment['x'] and pos.y == segment['y']:
                    return float('-inf')

        # Check for potential head-to-head collisions
        for opponent in self.opponents:
            opponent_head = Position(opponent['body'][0]['x'], opponent['body'][0]['y'])
            opponent_length = len(opponent['body'])
            
            if self._is_adjacent(pos, opponent_head):
                # If we're smaller or equal size, avoid head-to-head
                if self.my_length <= opponent_length:
                    safety_score -= 75
                # If we're larger, slightly prefer head-to-head
                else:
                    safety_score += 25

        # Penalize moves close to walls
        if pos.x == 0 or pos.x == self.board_width - 1:
            safety_score -= 20
        if pos.y == 0 or pos.y == self.board_height - 1:
            safety_score -= 20

        return safety_score

    def _is_adjacent(self, pos1: Position, pos2: Position) -> bool:
        """Check if two positions are adjacent."""
        return abs(pos1.x - pos2.x) + abs(pos1.y - pos2.y) == 1

    def evaluate_food_moves(self, base_moves: Dict[Direction, float]) -> Dict[Direction, float]:
        """Adjust move scores based on food positions."""
        if self.health < 50:  # More aggressive food seeking when health is low
            food_weight = 2.0
        elif self.health < 75:
            food_weight = 1.0
        else:
            food_weight = 0.5

        for direction, score in base_moves.items():
            if score == float('-inf'):
                continue

            next_pos = self._get_next_position(direction)
            closest_food = self._find_closest_food(next_pos)
            
            if closest_food:
                # Check if we're the closest snake to this food
                if self._am_closest_to_food(closest_food):
                    food_score = self._calculate_food_score(next_pos, closest_food)
                    base_moves[direction] += food_score * food_weight

        return base_moves

    def _find_closest_food(self, pos: Position) -> Optional[Position]:
        """Find the closest food pellet to a position."""
        min_distance = float('inf')
        closest_food = None
        
        for food in self.game_state['board']['food']:
            distance = abs(pos.x - food['x']) + abs(pos.y - food['y'])
            if distance < min_distance:
                min_distance = distance
                closest_food = Position(food['x'], food['y'])
                
        return closest_food

    def _am_closest_to_food(self, food: Position) -> bool:
        """Check if we're the closest snake to a food pellet."""
        my_distance = abs(self.my_head.x - food.x) + abs(self.my_head.y - food.y)
        
        for opponent in self.opponents:
            opponent_head = opponent['body'][0]
            opponent_distance = abs(opponent_head['x'] - food.x) + abs(opponent_head['y'] - food.y)
            if opponent_distance < my_distance:
                return False
        return True

    def _calculate_food_score(self, pos: Position, food: Position) -> float:
        """Calculate score modification based on distance to food."""
        distance = abs(pos.x - food.x) + abs(pos.y - food.y)
        return max(50 - distance * 5, 0)  # Decreasing score with distance

def move(game_state: Dict) -> Dict:
    """Main move function."""
    strategy = MovementStrategy(game_state)
    
    # Get base safe moves
    moves = strategy.get_safe_moves()
    
    # Adjust for food
    moves = strategy.evaluate_food_moves(moves)
    
    # Choose the best move
    best_move = max(moves.items(), key=lambda x: x[1])
    
    return {"move": best_move[0].value}
