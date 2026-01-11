import socket          # Модуль для роботи з мережею (TCP-зʼєднання)
import json            # Для перетворення Python-обʼєктів у JSON і назад
import threading       # Для роботи з потоками
import time            # Для затримок (sleep)
import random          # Для випадкового напрямку мʼяча
 
# Розміри ігрового поля
WIDTH, HEIGHT = 800, 600
 
# Швидкість мʼяча
BALL_SPEED = 5
 
# Швидкість ракетки
PADDLE_SPEED = 10
 
# Початковий відлік перед стартом гри
COUNTDOWN_START = 3
 
class GameServer:
    def __init__(self, host='localhost', port=8080):
        # Створюємо TCP-сокет
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
 
        # Привʼязуємо сервер до адреси і порту
        self.server.bind((host, port))
 
        # Дозволяємо підключення максимум 2 клієнтів
        self.server.listen(2)
        print("🎮 Server started")
 
        # Словник клієнтів: 0 і 1 — ID гравців
        self.clients = {0: None, 1: None}
 
        # Чи підключений кожен гравець
        self.connected = {0: False, 1: False}
 
        # Lock для захисту спільних даних між потоками
        self.lock = threading.Lock()
 
        # Скидаємо стан гри
        self.reset_game_state()
 
        # Подія для відтворення звуків (удар, стіна і т.д.)
        self.sound_event = None
 
    def reset_game_state(self):
        # Початкові позиції ракеток
        self.paddles = {0: 250, 1: 250}
 
        # Очки гравців
        self.scores = [0, 0]
 
        # Початковий стан мʼяча
        self.ball = {
            "x": WIDTH // 2,    # центр по X
            "y": HEIGHT // 2,   # центр по Y
            "vx": BALL_SPEED * random.choice([-1, 1]),  # напрямок по X
            "vy": BALL_SPEED * random.choice([-1, 1])   # напрямок по Y
        }
 
        # Таймер перед стартом
        self.countdown = COUNTDOWN_START
 
        # Прапорець завершення гри
        self.game_over = False
 
        # Переможець (None, поки гра триває)
        self.winner = None
 
    def handle_client(self, pid):
        # Беремо зʼєднання конкретного гравця
        conn = self.clients[pid]
        try:
            while True:
                # Отримуємо команду від клієнта
                data = conn.recv(64).decode()
 
                # Блокуємо доступ до спільних даних
                with self.lock:
                    if data == "UP":
                        # Рух ракетки вгору з обмеженням
                        self.paddles[pid] = max(60, self.paddles[pid] - PADDLE_SPEED)
                    elif data == "DOWN":
                        # Рух ракетки вниз з обмеженням
                        self.paddles[pid] = min(HEIGHT - 100, self.paddles[pid] + PADDLE_SPEED)
        except:
            # Якщо клієнт відʼєднався або сталася помилка
            with self.lock:
                self.connected[pid] = False
                self.game_over = True
                self.winner = 1 - pid  # інший гравець перемагає
                print(f"Гравець {pid} відключився. Переміг гравець {1 - pid}.")
 
    def broadcast_state(self):
        # Формуємо стан гри для клієнтів
        state = json.dumps({
            "paddles": self.paddles,
            "ball": self.ball,
            "scores": self.scores,
            "countdown": max(self.countdown, 0),
            "winner": self.winner if self.game_over else None,
            "sound_event": self.sound_event
        }) + "\n"
 
        # Надсилаємо стан усім підключеним клієнтам
        for pid, conn in self.clients.items():
            if conn:
                try:
                    conn.sendall(state.encode())
                except:
                    self.connected[pid] = False
 
    def ball_logic(self):
        # Відлік перед початком гри
        while self.countdown > 0:
            time.sleep(1)
            with self.lock:
                self.countdown -= 1
                self.broadcast_state()
 
        # Основний цикл гри
        while not self.game_over:
            with self.lock:
                # Рух мʼяча
                self.ball['x'] += self.ball['vx']
                self.ball['y'] += self.ball['vy']
 
                # Удар об верхню або нижню стіну
                if self.ball['y'] <= 60 or self.ball['y'] >= HEIGHT:
                    self.ball['vy'] *= -1
                    self.sound_event = "wall_hit"
 
                # Удар об ракетку
                if (self.ball['x'] <= 40 and self.paddles[0] <= self.ball['y'] <= self.paddles[0] + 100) or \
                   (self.ball['x'] >= WIDTH - 40 and self.paddles[1] <= self.ball['y'] <= self.paddles[1] + 100):
                    self.ball['vx'] *= -1
                    self.sound_event = 'platform_hit'
 
                # Якщо мʼяч вилетів за лівий край
                if self.ball['x'] < 0:
                    self.scores[1] += 1
                    self.reset_ball()
 
                # Якщо мʼяч вилетів за правий край
                elif self.ball['x'] > WIDTH:
                    self.scores[0] += 1
                    self.reset_ball()
 
                # Перевірка на перемогу
                if self.scores[0] >= 10:
                    self.game_over = True
                    self.winner = 0
                elif self.scores[1] >= 10:
                    self.game_over = True
                    self.winner = 1
 
                # Надсилаємо оновлений стан гри
                self.broadcast_state()
                self.sound_event = None
 
            # ~60 кадрів на секунду
            time.sleep(0.016)
 
    def reset_ball(self):
        # Скидання мʼяча в центр
        self.ball = {
            "x": WIDTH // 2,
            "y": HEIGHT // 2,
            "vx": BALL_SPEED * random.choice([-1, 1]),
            "vy": BALL_SPEED * random.choice([-1, 1])
        }
 
    def accept_players(self):
        # Чекаємо двох гравців
        for pid in [0, 1]:
            print(f"Очікуємо гравця {pid}...")
            conn, _ = self.server.accept()
            self.clients[pid] = conn
 
            # Надсилаємо клієнту його ID
            conn.sendall((str(pid) + "\n").encode())
            self.connected[pid] = True
 
            print(f"Гравець {pid} приєднався")
 
            # Запускаємо окремий потік для клієнта
            threading.Thread(
                target=self.handle_client,
                args=(pid,),
                daemon=True
            ).start()
 
    def run(self):
        while True:
            # Чекаємо гравців
            self.accept_players()
 
            # Скидаємо гру
            self.reset_game_state()
 
            # Запускаємо логіку мʼяча в окремому потоці
            threading.Thread(
                target=self.ball_logic,
                daemon=True
            ).start()
 
            # Чекаємо завершення гри
            while not self.game_over and all(self.connected.values()):
                time.sleep(0.1)
 
            print(f"Гравець {self.winner} переміг!")
            time.sleep(5)
 
            # Закриваємо старі зʼєднання
            for pid in [0, 1]:
                try:
                    self.clients[pid].close()
                except:
                    pass
                self.clients[pid] = None
                self.connected[pid] = False
 
# Створюємо сервер і запускаємо його
GameServer().run()