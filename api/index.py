import logging
import os
import typing
from flask import Flask, request, jsonify
from collections import deque
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Set, Tuple, Optional

# Initialize Flask app
app = Flask(__name__)

# Flask routes
@app.get("/")
def on_info():
    return info()

@app.post("/start")
def on_start():
    game_state = request.get_json()
    start(game_state)
    return "ok"

@app.post("/move")
def on_move():
    game_state = request.get_json()
    return move(game_state)

@app.post("/end")
def on_end():
    game_state = request.get_json()
    end(game_state)
    return "ok"

@app.after_request
def identify_server(response):
    response.headers.set("server", "battlesnake/github/starter-snake-python")
    return response

@app.errorhandler(500)
def internal_error(error):
    response = jsonify({"message": "Internal server error", "error": str(error)})
    response.status_code = 500
    return response

# Game logic classes
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

        # Additional safety calculations for tight spaces using flood fill
        space_score = self._calculate_flood_fill(pos)
        if space_score < self.my_length:
            safety_score -= (self.my_length - space_score) * 10

        # Penalize moves close to walls
        if pos.x == 0 or pos.x == self.board_width - 1:
            safety_score -= 20
        if pos.y == 0 or pos.y == self.board_height - 1:
            safety_score -= 20

        return safety_score

    def _calculate_flood_fill(self, start_pos: Position) -> int:
        """Calculate available space using flood fill algorithm."""
        board = [[0] * self.board_height for _ in range(self.board_width)]
        
        # Mark all snake bodies on the board
        for snake in self.game_state['board']['snakes']:
            # Don't consider the tail as an obstacle if we're not going to grow
            segments_to_mark = snake['body'][:-1] if snake['id'] == self.my_snake['id'] and self.health < 100 else snake['body']
            for segment in segments_to_mark:
                board[segment['x']][segment['y']] = 1

        def flood_fill_recursive(x: int, y: int, visited: set) -> int:
            # Check boundaries and obstacles
            if (x, y) in visited or \
               x < 0 or x >= self.board_width or \
               y < 0 or y >= self.board_height or \
               board[x][y] == 1:
                return 0
            
            visited.add((x, y))
            
            # Recursively explore all directions
            space = 1
            for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                space += flood_fill_recursive(x + dx, y + dy, visited)
            
            return space

        return flood_fill_recursive(start_pos.x, start_pos.y, set())

    def _calculate_position_safety(self, pos: Position) -> float:
        """Calculate safety score for a position."""
        safety_score = 100.0

        # Check for immediate collisions with snake bodies
        for snake in self.game_state['board']['snakes']:
            for segment in snake['body'][:-1]:  # Exclude tail
                if pos.x == segment['x'] and pos.y == segment['y']:
                    return float('-inf')

        # Calculate available space using flood fill
        available_space = self._calculate_flood_fill(pos)
        
        # Strongly penalize moves that lead to spaces smaller than our length
        if available_space <= self.my_length:
            safety_score -= max(0, (self.my_length - available_space) * 30)
        
        # Give bonus for moves that lead to larger spaces
        else:
            safety_score += min(50, available_space / 2)

        # Check for potential head-to-head collisions
        for opponent in self.opponents:
            opponent_head = Position(opponent['body'][0]['x'], opponent['body'][0]['y'])
            opponent_length = len(opponent['body'])
            
            if self._is_adjacent(pos, opponent_head):
                # If we're smaller or equal size, strongly avoid head-to-head
                if self.my_length <= opponent_length:
                    safety_score -= 150
                # If we're larger, slightly prefer head-to-head
                else:
                    safety_score += 25

        # Penalize moves close to walls, but less severely than before
        if pos.x == 0 or pos.x == self.board_width - 1:
            safety_score -= 10
        if pos.y == 0 or pos.y == self.board_height - 1:
            safety_score -= 10

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

# Game state functions
def info() -> typing.Dict:
    print("INFO")
    return {
        "apiversion": "1",
        "author": "Finlay",  # TODO: Your name here
        "color": "#12A434",
        "head": "lantern-fish",
        "tail": "do-sammy",
    }

def start(game_state: typing.Dict):
    print(f"GAME START -> {game_state['game']['id']}")

def end(game_state: typing.Dict):
    print(f"GAME OVER -> {game_state['game']['id']}")

def move(game_state: typing.Dict) -> typing.Dict:
    """Main move function."""
    strategy = MovementStrategy(game_state)
    
    # Get base safe moves
    moves = strategy.get_safe_moves()
    
    # Adjust for food
    moves = strategy.evaluate_food_moves(moves)
    
    # Choose the best move
    best_move = max(moves.items(), key=lambda x: x[1])
    
    # Debug logging
    print(f"Moves evaluation: {moves}")
    print(f"Chosen move: {best_move[0].value} with score {best_move[1]}")
    
    return {"move": best_move[0].value}

if __name__ == "__main__":
    host = "0.0.0.0"
    port = int(os.environ.get("PORT", "8000"))
    
    logging.getLogger("werkzeug").setLevel(logging.ERROR)
    
    print(f"\nRunning Battlesnake at http://{host}:{port}")
    app.run(host=host, port=port)
