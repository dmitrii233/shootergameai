"""
2D шутер с видом сверху на Pygame.

Управление:
    WASD  — движение
    Мышь  — прицеливание
    ЛКМ   — стрельба (можно зажать)
    ESC   — пауза
    SPACE — начать игру / рестарт
    1/2/3 — выбор улучшения после босса

Враги появляются волнами, с каждой волной становятся сильнее.
Каждые 5 волн появляется босс.
"""

import math
import random
from array import array

import pygame

# ---------------------------------------------------------------------------
# Константы
# ---------------------------------------------------------------------------
WIDTH, HEIGHT = 1280, 720
FPS = 60

# Цвета
BG_COLOR       = (22, 24, 32)
GRID_COLOR     = (34, 38, 50)
PLAYER_COLOR   = (90, 160, 255)
PLAYER_DARK    = (50, 100, 190)
BULLET_COLOR   = (255, 230, 120)
BLOOD_COLOR    = (200, 60, 60)
TEXT_COLOR     = (235, 235, 235)
HP_COLOR       = (80, 220, 110)
HP_BG          = (60, 64, 74)
HURT_COLOR     = (255, 60, 60)

# Игрок
PLAYER_RADIUS     = 16
PLAYER_SPEED      = 320.0
PLAYER_MAX_HP     = 100
SHOOT_COOLDOWN    = 0.14   # сек
BULLET_SPEED      = 850.0
BULLET_DAMAGE     = 25
BULLET_RADIUS     = 5
INVULN_TIME       = 0.6    # сек после получения урона

# Волны
WAVE_TIME         = 12     # сек на волну
SPAWN_DELAY_START = 1.1    # начальная задержка между спавнами
SPAWN_DELAY_MIN   = 0.28

# Типы врагов: имя -> характеристики
ENEMY_TYPES = {
    "basic": dict(radius=18, speed=95,  hp=40,  color=(80, 200, 130), damage=10, score=10),
    "fast":  dict(radius=13, speed=170, hp=20,  color=(235, 215, 70), damage=7,  score=15),
    "tank":  dict(radius=27, speed=55,  hp=110, color=(220, 95, 95),  damage=20, score=30),
}
BOSS_TYPES = {
    "boss":  dict(radius=45, speed=40,  hp=600, color=(170, 90, 220), damage=35, score=150),
}

# Бафы (подбираемые предметы)
BUFF_TYPES = {
    "heal":   dict(color=(80, 220, 110),  label="+",  lifetime=20.0),
    "rapid":  dict(color=(255, 205, 70),  label="F",  lifetime=15.0),
    "speed":  dict(color=(120, 195, 255), label="S",  lifetime=15.0),
    "damage": dict(color=(255, 125, 125), label="D",  lifetime=15.0),
    "shield": dict(color=(170, 225, 255), label="Щ",  lifetime=15.0),
}
BUFF_WEIGHTS = [("heal", 35), ("rapid", 20), ("speed", 20), ("damage", 15), ("shield", 10)]
MAX_BUFFS_ON_MAP = 3
BUFF_SPAWN_MIN, BUFF_SPAWN_MAX = 6.0, 9.0

HEAL_AMOUNT                  = 35
RAPID_TIME, RAPID_COOLDOWN_MULT = 10.0, 0.5
SPEED_TIME, SPEED_MULT       = 10.0, 1.5
DAMAGE_TIME, DAMAGE_MULT     = 10.0, 2.0
SHIELD_TIME                  = 7.0

# Улучшения после убийства босса (постоянные и слабее бафов)
UPGRADES = {
    "hp":      dict(title="+15 к здоровью",      desc="Максимум HP +15, мгновенно лечит +15",
                    color=(80, 220, 110), rarity="common"),
    "damage":  dict(title="Урон +10%",           desc="Урон выстрела +10%",
                    color=(255, 125, 125), rarity="common"),
    "fire":    dict(title="Скорострельность +7%", desc="Перезарядка −7%",
                    color=(255, 205, 70), rarity="common"),
    "pierce":  dict(title="Пробитие +1",         desc="Пуля пробивает на 1 врага больше",
                    color=(200, 165, 255), rarity="common"),
    "speed":   dict(title="Скорость +8%",        desc="Скорость передвижения +8%",
                    color=(120, 195, 255), rarity="common"),
    "regen":   dict(title="Регенерация",         desc="+1 HP каждую секунду",
                    color=(120, 255, 170), rarity="rare"),
    "vampire": dict(title="Вампиризм",           desc="+2 HP за убийство врага",
                    color=(255, 90, 155), rarity="rare"),
}
RARE_CHANCE = 0.18            # шанс редкого улучшения в одном из слотов

UPGRADE_HP_BONUS       = 15
UPGRADE_DAMAGE_MULT    = 1.10
UPGRADE_FIRE_MULT      = 0.93
UPGRADE_SPEED_MULT     = 1.08
UPGRADE_MAX_PIERCE     = 3
UPGRADE_REGEN_AMOUNT   = 1.0
UPGRADE_VAMPIRE_AMOUNT = 2


# ---------------------------------------------------------------------------
# Звуковые эффекты (генерируются программно, без внешних файлов)
# ---------------------------------------------------------------------------
class Sounds:
    """Простое хранилище звуков. Если звук недоступен — игра продолжается без него."""

    enabled = False

    @classmethod
    def init(cls):
        try:
            pygame.mixer.pre_init(22050, -16, 1, 256)
            pygame.mixer.init()
            cls.shoot = cls._make_sound(880, 0.07, 0.25, "noise")
            cls.hit = cls._make_sound(320, 0.08, 0.3, "square")
            cls.kill = cls._make_sound(200, 0.18, 0.35, "square")
            cls.hurt = cls._make_sound(140, 0.25, 0.4, "saw")
            cls.boss = cls._make_sound(70, 0.6, 0.45, "saw")
            cls.powerup = cls._make_sound(520, 0.18, 0.35, "sweep")
            cls.enabled = True
        except pygame.error:
            cls.enabled = False

    @staticmethod
    def _make_sound(freq, duration, volume, kind):
        rate = 22050
        frames = int(rate * duration)
        buf = array("h")
        for i in range(frames):
            t = i / rate
            # простой синтез волн + затухание
            env = max(0.0, 1.0 - t / duration)
            if kind == "square":
                sample = 1.0 if (freq * t) % 1.0 < 0.5 else -1.0
            elif kind == "saw":
                sample = 2.0 * ((freq * t) % 1.0) - 1.0
            elif kind == "sweep":
                f = freq * (1.0 + 2.0 * t / duration)  # нарастающая частота
                sample = 1.0 if (f * t) % 1.0 < 0.5 else -1.0
            else:  # шум с быстрым затуханием
                sample = random.uniform(-1.0, 1.0)
            value = int(32767 * volume * env * sample)
            buf.append(value)
        return pygame.mixer.Sound(buffer=buf.tobytes())

    @classmethod
    def play(cls, name):
        if cls.enabled:
            try:
                getattr(cls, name).play()
            except (AttributeError, pygame.error):
                pass


# ---------------------------------------------------------------------------
# Частицы (эффекты взрывов/попаданий)
# ---------------------------------------------------------------------------
class Particle:
    def __init__(self, x, y, color, speed, life, size=3, spread=360.0):
        angle = math.radians(random.uniform(0.0, spread))
        vel = random.uniform(speed * 0.3, speed)
        self.x = x
        self.y = y
        self.vx = math.cos(angle) * vel
        self.vy = math.sin(angle) * vel
        self.color = color
        self.life = life
        self.max_life = life
        self.size = random.uniform(size * 0.5, size)

    def update(self, dt):
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.vx *= 0.94
        self.vy *= 0.94
        self.life -= dt
        return self.life > 0

    def draw(self, screen):
        alpha = max(0.0, self.life / self.max_life)
        radius = max(1, int(self.size * alpha))
        color = tuple(int(c * alpha + 0.5) for c in self.color)
        pygame.draw.circle(screen, color, (int(self.x), int(self.y)), radius)


def spawn_blood(x, y, particles, amount=10):
    for _ in range(amount):
        particles.append(Particle(x, y, BLOOD_COLOR, 180.0, random.uniform(0.25, 0.6), 4))


def spawn_explosion(x, y, particles, color, amount=16):
    for _ in range(amount):
        particles.append(Particle(x, y, color, 260.0, random.uniform(0.3, 0.8), 5))


def point_segment_dist2(px, py, ax, ay, bx, by):
    """Квадрат расстояния от точки (px, py) до отрезка (a-b). Для swept-коллизий."""
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return (px - ax) ** 2 + (py - ay) ** 2
    t = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    cx, cy = ax + t * dx, ay + t * dy
    return (px - cx) ** 2 + (py - cy) ** 2


# ---------------------------------------------------------------------------
# Игрок
# ---------------------------------------------------------------------------
class Player:
    def __init__(self):
        self.pos = pygame.Vector2(WIDTH / 2, HEIGHT / 2)
        self.radius = PLAYER_RADIUS
        self.hp = PLAYER_MAX_HP
        self.max_hp = PLAYER_MAX_HP
        self.angle = 0.0              # направление взгляда (радианы)
        self.shoot_timer = 0.0
        self.invuln_timer = 0.0
        self.hurt_timer = 0.0
        # эффекты бафов
        self.rapid_timer = 0.0
        self.speed_timer = 0.0
        self.damage_timer = 0.0
        self.shield_timer = 0.0
        # постоянные улучшения (за убийство босса)
        self.perm_damage_mult = 1.0
        self.perm_fire_mult = 1.0
        self.perm_speed_mult = 1.0
        self.pierce = 0
        self.regen = 0.0
        self.vampire = 0
        self.alive = True
        self._base_surface = self._make_ship()

    @staticmethod
    def _make_ship():
        """Кораблик, смотрящий вправо (угол 0 = +X)."""
        size = 48
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        cx = size / 2
        # корпус — стрелка
        points = [
            (cx + 22, cx),          # нос
            (cx - 16, cx - 15),     # верхний хвост
            (cx - 14, cx),          # выемка
            (cx - 16, cx + 15),     # нижний хвост
        ]
        pygame.draw.polygon(surf, PLAYER_COLOR, points)
        pygame.draw.polygon(surf, PLAYER_DARK, points, 3)
        # кокпит
        pygame.draw.circle(surf, (200, 225, 255), (int(cx + 4), int(cx)), 5)
        return surf

    def update(self, dt, keys):
        if not self.alive:
            return
        # движение
        move = pygame.Vector2()
        if keys[pygame.K_w]:
            move.y -= 1
        if keys[pygame.K_s]:
            move.y += 1
        if keys[pygame.K_a]:
            move.x -= 1
        if keys[pygame.K_d]:
            move.x += 1
        speed = PLAYER_SPEED * self.perm_speed_mult \
            * (SPEED_MULT if self.speed_timer > 0 else 1.0)
        if move.length_squared() > 0:
            move = move.normalize() * speed
        self.pos += move * dt
        # привязка к экрану
        self.pos.x = max(self.radius, min(WIDTH - self.radius, self.pos.x))
        self.pos.y = max(self.radius, min(HEIGHT - self.radius, self.pos.y))

        # прицеливание
        mx, my = pygame.mouse.get_pos()
        self.angle = math.atan2(my - self.pos.y, mx - self.pos.x)

        # таймеры (включая эффекты бафов)
        self.shoot_timer = max(0.0, self.shoot_timer - dt)
        self.invuln_timer = max(0.0, self.invuln_timer - dt)
        self.hurt_timer = max(0.0, self.hurt_timer - dt)
        self.rapid_timer = max(0.0, self.rapid_timer - dt)
        self.speed_timer = max(0.0, self.speed_timer - dt)
        self.damage_timer = max(0.0, self.damage_timer - dt)
        self.shield_timer = max(0.0, self.shield_timer - dt)

        # регенерация
        if self.regen > 0:
            self.hp = min(self.max_hp, self.hp + self.regen * dt)

    def try_shoot(self, bullets, particles):
        """Выстрел при зажатой ЛКМ. True, если выстрел сделан."""
        if not self.alive or self.shoot_timer > 0:
            return False
        cooldown = SHOOT_COOLDOWN * self.perm_fire_mult \
            * (RAPID_COOLDOWN_MULT if self.rapid_timer > 0 else 1.0)
        self.shoot_timer = cooldown
        # пуля вылетает из носа корабля
        muzzle_offset = self.radius + 14
        bx = self.pos.x + math.cos(self.angle) * muzzle_offset
        by = self.pos.y + math.sin(self.angle) * muzzle_offset
        vel = pygame.Vector2(math.cos(self.angle), math.sin(self.angle)) * BULLET_SPEED
        damage = BULLET_DAMAGE * self.perm_damage_mult \
            * (DAMAGE_MULT if self.damage_timer > 0 else 1.0)
        bullets.append(Bullet(bx, by, vel, damage, BULLET_RADIUS, BULLET_COLOR,
                              self.pierce))
        spawn_explosion(bx, by, particles, BULLET_COLOR, 3)
        Sounds.play("shoot")
        return True

    def take_damage(self, amount):
        if self.invuln_timer > 0 or not self.alive or self.shield_timer > 0:
            return
        self.hp -= amount
        self.invuln_timer = INVULN_TIME
        self.hurt_timer = 0.18
        Sounds.play("hurt")
        if self.hp <= 0:
            self.hp = 0
            self.alive = False

    def apply_buff(self, buff):
        """Применение подобранного бафа."""
        if buff.kind == "heal":
            self.hp = min(self.max_hp, self.hp + HEAL_AMOUNT)
        elif buff.kind == "rapid":
            self.rapid_timer = RAPID_TIME
        elif buff.kind == "speed":
            self.speed_timer = SPEED_TIME
        elif buff.kind == "damage":
            self.damage_timer = DAMAGE_TIME
        elif buff.kind == "shield":
            self.shield_timer = SHIELD_TIME

    def apply_upgrade(self, kind):
        """Постоянное улучшение за убийство босса (слабее бафов)."""
        if kind == "hp":
            self.max_hp += UPGRADE_HP_BONUS
            self.hp = min(self.max_hp, self.hp + UPGRADE_HP_BONUS)
        elif kind == "damage":
            self.perm_damage_mult *= UPGRADE_DAMAGE_MULT
        elif kind == "fire":
            self.perm_fire_mult *= UPGRADE_FIRE_MULT
        elif kind == "pierce":
            self.pierce = min(UPGRADE_MAX_PIERCE, self.pierce + 1)
        elif kind == "speed":
            self.perm_speed_mult *= UPGRADE_SPEED_MULT
        elif kind == "regen":
            self.regen += UPGRADE_REGEN_AMOUNT
        elif kind == "vampire":
            self.vampire += UPGRADE_VAMPIRE_AMOUNT

    def draw(self, screen):
        if not self.alive:
            return
        # мигание при неуязвимости
        if self.invuln_timer > 0 and int(self.invuln_timer * 12) % 2 == 0:
            return
        rotated = pygame.transform.rotate(self._base_surface,
                                         -math.degrees(self.angle))
        rect = rotated.get_rect(center=(int(self.pos.x), int(self.pos.y)))
        screen.blit(rotated, rect)
        # красный контур при получении урона
        if self.hurt_timer > 0:
            pygame.draw.circle(screen, HURT_COLOR,
                               (int(self.pos.x), int(self.pos.y)),
                               self.radius + 4, 2)
        # щит-пузырь
        if self.shield_timer > 0:
            pygame.draw.circle(screen, (150, 220, 255),
                               (int(self.pos.x), int(self.pos.y)),
                               self.radius + 9, 3)


# ---------------------------------------------------------------------------
# Пули
# ---------------------------------------------------------------------------
class Bullet:
    def __init__(self, x, y, velocity, damage, radius, color, pierce=0):
        self.pos = pygame.Vector2(x, y)
        self.prev_pos = pygame.Vector2(x, y)
        self.velocity = velocity
        self.damage = damage
        self.radius = radius
        self.color = color
        # пробитие: сколько врагов пуля проходит насквозь.
        # 0 — исчезает на первом же враге, 1 — проходит первого и гибнет на втором и т.д.
        self.pierce = pierce
        # враги, которых эта пуля уже пробила (чтобы не бить одного дважды)
        self.hit_enemies = set()

    def update(self, dt):
        self.prev_pos.update(self.pos)
        self.pos += self.velocity * dt
        # за пределами экрана пуля исчезает
        return -50 <= self.pos.x <= WIDTH + 50 and -50 <= self.pos.y <= HEIGHT + 50

    def draw(self, screen):
        # след-хвост, чтобы траектория полёта была хорошо видна
        pygame.draw.line(screen, self.color, self.prev_pos, self.pos, 4)
        if self.pierce > 0:
            # пробивающая пуля подсвечена кольцом
            pygame.draw.circle(screen, (255, 220, 130),
                               (int(self.pos.x), int(self.pos.y)),
                               self.radius + 3, 2)
        pygame.draw.circle(screen, self.color,
                           (int(self.pos.x), int(self.pos.y)), self.radius)
        pygame.draw.circle(screen, (255, 255, 255),
                           (int(self.pos.x), int(self.pos.y)), self.radius - 2)


# ---------------------------------------------------------------------------
# Враги
# ---------------------------------------------------------------------------
class Enemy:
    def __init__(self, kind, hp_mult=1.0, speed_mult=1.0):
        stats = (BOSS_TYPES if kind == "boss" else ENEMY_TYPES)[kind]
        self.kind = kind
        self.radius = stats["radius"]
        self.speed = stats["speed"] * speed_mult
        self.max_hp = int(stats["hp"] * hp_mult)
        self.hp = self.max_hp
        self.damage = stats["damage"]
        self.score = stats["score"]
        self.color = stats["color"]
        self.is_boss = kind == "boss"

        # спавн за пределами экрана
        side = random.randint(0, 3)
        if side == 0:    # сверху
            self.pos = pygame.Vector2(random.uniform(0, WIDTH), -40)
        elif side == 1:  # снизу
            self.pos = pygame.Vector2(random.uniform(0, WIDTH), HEIGHT + 40)
        elif side == 2:  # слева
            self.pos = pygame.Vector2(-40, random.uniform(0, HEIGHT))
        else:            # справа
            self.pos = pygame.Vector2(WIDTH + 40, random.uniform(0, HEIGHT))

        self.hit_flash = 0.0
        self.contact_timer = 0.0
        self.angle = 0.0   # направление движения, обновляется в update()

    def update(self, dt, player, particles):
        self.hit_flash = max(0.0, self.hit_flash - dt)
        self.contact_timer = max(0.0, self.contact_timer - dt)

        # движение к игроку
        direction = player.pos - self.pos
        if direction.length_squared() > 1:
            direction = direction.normalize()
        self.angle = math.atan2(direction.y, direction.x)
        self.pos += direction * self.speed * dt

        # урон при контакте (постоянный, но не каждый кадр)
        if self.contact_timer == 0.0:
            dist = self.pos.distance_to(player.pos)
            if dist < self.radius + player.radius:
                player.take_damage(self.damage)
                self.contact_timer = 0.5
                # отбрасываем врага
                self.pos -= direction * 14
                spawn_blood(player.pos.x, player.pos.y, particles, 8)

    def take_damage(self, amount, particles):
        self.hp -= amount
        self.hit_flash = 0.08
        spawn_blood(self.pos.x, self.pos.y, particles, 4)
        Sounds.play("hit")
        return self.hp <= 0

    def draw(self, screen):
        # дрожание при попадании
        jx = self.pos.x + random.uniform(-2, 2) * (self.hit_flash > 0)
        jy = self.pos.y + random.uniform(-2, 2) * (self.hit_flash > 0)
        color = (255, 255, 255) if self.hit_flash > 0 else self.color
        pygame.draw.circle(screen, color, (int(jx), int(jy)), self.radius)
        # "глаза", смотрящие на игрока
        if not self.is_boss:
            forward = pygame.Vector2(math.cos(self.angle), math.sin(self.angle))
            perp = pygame.Vector2(-forward.y, forward.x)
            for side in (-1, 1):
                eye = pygame.Vector2(jx, jy) + forward * (self.radius * 0.35) \
                    + perp * side * (self.radius * 0.4)
                pygame.draw.circle(screen, (30, 32, 40),
                                   (int(eye.x), int(eye.y)), int(self.radius * 0.22))
        # полоска здоровья
        bar_w = self.radius * 2
        ratio = self.hp / self.max_hp
        pygame.draw.rect(screen, HP_BG,
                         (jx - bar_w / 2, jy - self.radius - 10, bar_w, 5))
        pygame.draw.rect(screen, HP_COLOR,
                         (jx - bar_w / 2, jy - self.radius - 10, bar_w * ratio, 5))
        if self.is_boss:
            pygame.draw.circle(screen, color, (int(jx), int(jy)), self.radius, 4)


# ---------------------------------------------------------------------------
# Бафы (подбираемые предметы)
# ---------------------------------------------------------------------------
class Buff:
    """Предмет на карте: лечит или даёт временный эффект."""

    def __init__(self, kind):
        data = BUFF_TYPES[kind]
        self.kind = kind
        self.color = data["color"]
        self.label = data["label"]
        self.lifetime = data["lifetime"]
        self.time_left = self.lifetime
        self.radius = 15
        self.pos = pygame.Vector2(random.uniform(70, WIDTH - 70),
                                  random.uniform(90, HEIGHT - 90))

    def update(self, dt):
        """Уменьшает время жизни. False — баф истёк и должен исчезнуть."""
        self.time_left -= dt
        return self.time_left > 0

    def draw(self, screen, font):
        # мигание перед исчезновением
        if self.time_left < 3.0 and int(self.time_left * 6) % 2 == 0:
            return
        pulse = 1.0 + 0.1 * math.sin(pygame.time.get_ticks() / 160)
        r = int(self.radius * pulse)
        x, y = int(self.pos.x), int(self.pos.y)
        pygame.draw.circle(screen, (10, 12, 18), (x, y), r + 3)      # тень
        pygame.draw.circle(screen, self.color, (x, y), r)
        pygame.draw.circle(screen, (255, 255, 255), (x, y), r, 2)    # обводка
        label = font.render(self.label, True, (20, 22, 30))
        screen.blit(label, label.get_rect(center=(x, y)))


# ---------------------------------------------------------------------------
# Спавнер волн
# ---------------------------------------------------------------------------
class WaveManager:
    def __init__(self):
        self.wave = 1
        self.time_left = WAVE_TIME
        self.spawn_timer = 0.0
        self.boss_alert = 0.0

    def update(self, dt, enemies, player, particles):
        self.time_left -= dt
        if self.time_left <= 0:
            self.wave += 1
            self.time_left = WAVE_TIME
            # каждые 5 волн — босс
            if self.wave % 5 == 0:
                enemies.append(Enemy("boss",
                                     hp_mult=1.0 + self.wave * 0.1,
                                     speed_mult=1.0))
                self.boss_alert = 3.0
                Sounds.play("boss")
        # спавн обычных врагов
        self.spawn_timer -= dt
        if self.spawn_timer <= 0:
            self._spawn_enemy(enemies, player)
            delay = max(SPAWN_DELAY_MIN, SPAWN_DELAY_START - self.wave * 0.06)
            self.spawn_timer = delay * random.uniform(0.6, 1.4)
        self.boss_alert = max(0.0, self.boss_alert - dt)

    def _spawn_enemy(self, enemies, player):
        hp_mult = 1.0 + self.wave * 0.12
        speed_mult = 1.0 + self.wave * 0.02

        # доступные типы по волне
        pool = ["basic"]
        if self.wave >= 2:
            pool.append("fast")
        if self.wave >= 3:
            pool.append("tank")
            pool.append("tank")
        kind = random.choice(pool)

        # не спавнить слишком близко к игроку
        for _ in range(5):
            e = Enemy(kind, hp_mult, speed_mult)
            if e.pos.distance_to(player.pos) > 300 or self.wave <= 1:
                enemies.append(e)
                return

    def draw_boss_alert(self, screen, font):
        if self.boss_alert > 0:
            alpha = 255 if self.boss_alert > 2.5 else int(255 * self.boss_alert)
            text = font.render("ВНИМАНИЕ: БОСС!", True, (255, 120, 120))
            rect = text.get_rect(center=(WIDTH // 2, HEIGHT // 3))
            screen.blit(text, rect)


# ---------------------------------------------------------------------------
# Отрисовка фона
# ---------------------------------------------------------------------------
class Background:
    def __init__(self):
        self.surface = pygame.Surface((WIDTH, HEIGHT))
        self.surface.fill(BG_COLOR)
        for x in range(0, WIDTH, 48):
            pygame.draw.line(self.surface, GRID_COLOR, (x, 0), (x, HEIGHT))
        for y in range(0, HEIGHT, 48):
            pygame.draw.line(self.surface, GRID_COLOR, (0, y), (WIDTH, y))

    def draw(self, screen, offset=0):
        screen.blit(self.surface, (offset, 0))


# ---------------------------------------------------------------------------
# Интерфейс
# ---------------------------------------------------------------------------
def draw_hud(screen, fonts, player, score, wave, kills):
    # здоровье
    bar_w, bar_h = 320, 22
    x, y = 24, 24
    ratio = max(0.0, player.hp / player.max_hp)
    pygame.draw.rect(screen, HP_BG, (x, y, bar_w, bar_h), border_radius=6)
    pygame.draw.rect(screen, HP_COLOR,
                     (x, y, bar_w * ratio, bar_h), border_radius=6)
    pygame.draw.rect(screen, (255, 255, 255), (x, y, bar_w, bar_h), 2, border_radius=6)
    hp_text = fonts["small"].render(f"ЗДОРОВЬЕ: {player.hp}/{player.max_hp}",
                                    True, TEXT_COLOR)
    screen.blit(hp_text, (x + 4, y + 2))

    # активные бафы
    active = []
    if player.speed_timer > 0:
        active.append(("speed", player.speed_timer))
    if player.rapid_timer > 0:
        active.append(("rapid", player.rapid_timer))
    if player.damage_timer > 0:
        active.append(("damage", player.damage_timer))
    if player.shield_timer > 0:
        active.append(("shield", player.shield_timer))
    if active:
        panel_x, panel_y = 24, 58
        pygame.draw.rect(screen, (30, 34, 44),
                         (panel_x - 8, panel_y - 6, len(active) * 92 + 6, 40),
                         border_radius=8)
        for kind, remain in active:
            data = BUFF_TYPES[kind]
            pygame.draw.rect(screen, data["color"], (panel_x, panel_y, 26, 26),
                             border_radius=6)
            label = fonts["small"].render(data["label"], True, (15, 17, 24))
            screen.blit(label, label.get_rect(center=(panel_x + 13, panel_y + 13)))
            time_text = fonts["small"].render(f"{remain:.1f}", True, TEXT_COLOR)
            screen.blit(time_text, (panel_x + 32, panel_y + 3))
            panel_x += 92

    # счёт и волна
    score_text = fonts["hud"].render(f"СЧЁТ: {score}", True, TEXT_COLOR)
    screen.blit(score_text, (WIDTH - score_text.get_width() - 24, 20))
    wave_text = fonts["hud"].render(f"ВОЛНА: {wave}", True, TEXT_COLOR)
    screen.blit(wave_text, (WIDTH - wave_text.get_width() - 24, 56))
    kills_text = fonts["small"].render(f"Убито: {kills}", True, (160, 165, 180))
    screen.blit(kills_text, (WIDTH - kills_text.get_width() - 24, 92))


def draw_center_message(screen, fonts, title, subtitle):
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 160))
    screen.blit(overlay, (0, 0))
    title_surf = fonts["title"].render(title, True, TEXT_COLOR)
    screen.blit(title_surf, title_surf.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 80)))
    sub_surf = fonts["big"].render(subtitle, True, (180, 190, 210))
    screen.blit(sub_surf, sub_surf.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 10)))


def wrap_text(font, text, max_width):
    """Разбивает текст на строки по ширине (для карточек улучшений)."""
    lines, current = [], ""
    for word in text.split():
        candidate = (current + " " + word).strip()
        if font.size(candidate)[0] <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


# ---------------------------------------------------------------------------
# Игра
# ---------------------------------------------------------------------------
class Game:
    def __init__(self):
        Sounds.init()   # сначала аудио (pre_init до основного init)
        pygame.init()
        pygame.display.set_caption("2D Shooter — вид сверху")
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        self.clock = pygame.time.Clock()

        self.fonts = {
            "small": pygame.font.SysFont("Arial", 22),
            "hud": pygame.font.SysFont("Arial", 30, bold=True),
            "big": pygame.font.SysFont("Arial", 40),
            "title": pygame.font.SysFont("Arial", 72, bold=True),
        }
        self.background = Background()
        self.state = "menu"     # menu / playing / paused / gameover
        # атрибуты, заполняемые в reset(), с дефолтами для меню
        self.score = 0
        self.kills = 0
        self.shake = 0.0
        self.waves = None
        self.player = None
        self.buffs = []
        self.upgrade_options = []
        self.upgrade_rects = []

    # -------------------------------------------------------------- ресурсы
    def reset(self):
        self.player = Player()
        self.bullets = []
        self.enemies = []
        self.particles = []
        self.waves = WaveManager()
        self.score = 0
        self.kills = 0
        self.shake = 0.0
        self.buffs = []
        self.buff_spawn_timer = 3.0   # первый баф через 3 секунды
        self.upgrade_options = []
        self.upgrade_rects = []
        pygame.mouse.set_pos(WIDTH // 2, HEIGHT // 2)

    # -------------------------------------------------------------- ввод
    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if self.state == "playing":
                        self.state = "paused"
                    elif self.state == "paused":
                        self.state = "playing"

                if self.state == "menu" and event.key == pygame.K_SPACE:
                    self.reset()
                    self.state = "playing"

                elif self.state == "gameover":
                    if event.key in (pygame.K_r, pygame.K_SPACE):
                        self.reset()
                        self.state = "playing"
                    elif event.key == pygame.K_ESCAPE:
                        self.state = "menu"

                elif self.state == "paused" and event.key in (pygame.K_r, pygame.K_SPACE):
                    self.state = "playing"

                elif self.state == "upgrading" and event.key in (pygame.K_1, pygame.K_2, pygame.K_3):
                    self._choose_upgrade({pygame.K_1: 0, pygame.K_2: 1,
                                          pygame.K_3: 2}[event.key])

            if self.state == "upgrading" and event.type == pygame.MOUSEBUTTONDOWN \
                    and event.button == 1:
                for i, rect in enumerate(self.upgrade_rects):
                    if rect.collidepoint(event.pos):
                        self._choose_upgrade(i)
                        break

        if self.state == "playing":
            mouse = pygame.mouse.get_pressed()
            if mouse[0]:
                self.player.try_shoot(self.bullets, self.particles)
        return True

    # -------------------------------------------------------------- логика
    def update(self, dt):
        if self.state != "playing":
            return

        keys = pygame.key.get_pressed()
        self.player.update(dt, keys)

        # пули
        self.bullets = [b for b in self.bullets if b.update(dt)]

        # враги
        for e in self.enemies:
            e.update(dt, self.player, self.particles)

        # столкновения пуль с врагами (Swept-коллизии: пуля не может "проскочить")
        for bullet in self.bullets[:]:
            for enemy in self.enemies[:]:
                # этого врага пуля уже пробила ранее — не бьём повторно
                if enemy in bullet.hit_enemies:
                    continue
                r_sum = bullet.radius + enemy.radius
                d2 = point_segment_dist2(enemy.pos.x, enemy.pos.y,
                                         bullet.prev_pos.x, bullet.prev_pos.y,
                                         bullet.pos.x, bullet.pos.y)
                if d2 >= r_sum * r_sum:
                    continue
                died = enemy.take_damage(bullet.damage, self.particles)
                if died:
                    self.enemies.remove(enemy)
                    spawn_explosion(enemy.pos.x, enemy.pos.y,
                                    self.particles, enemy.color, 18)
                    Sounds.play("kill")
                    self.score += enemy.score
                    self.kills += 1
                    if self.player.vampire > 0:
                        self.player.hp = min(self.player.max_hp,
                                             self.player.hp + self.player.vampire)
                    if enemy.is_boss:
                        self.shake = 0.7
                        self.start_upgrade_selection()
                if bullet.pierce > 0:
                    # пуля проходит сквозь врага: тратим пробитие и летим дальше,
                    # враг запоминается, чтобы урон не был нанесён ему повторно
                    bullet.pierce -= 1
                    bullet.hit_enemies.add(enemy)
                    spawn_explosion(bullet.pos.x, bullet.pos.y,
                                    self.particles, (255, 250, 200), 4)
                    # в один кадр пуля может задеть и следующих врагов на пути
                else:
                    # пробитие закончилось — пуля гаснет на этом враге
                    if bullet in self.bullets:
                        self.bullets.remove(bullet)
                    break

        # волны
        self.waves.update(dt, self.enemies, self.player, self.particles)

        # бафы
        self._update_buffs(dt)

        # частицы
        self.particles = [p for p in self.particles if p.update(dt)]

        # провал
        if not self.player.alive:
            self.state = "gameover"
            spawn_explosion(self.player.pos.x, self.player.pos.y,
                            self.particles, PLAYER_COLOR, 40)

        self.shake = max(0.0, self.shake - dt)

    # -------------------------------------------------------------- бафы
    def _update_buffs(self, dt):
        # спавн нового бафа
        self.buff_spawn_timer -= dt
        if self.buff_spawn_timer <= 0 and len(self.buffs) < MAX_BUFFS_ON_MAP:
            self.spawn_buff()
            self.buff_spawn_timer = random.uniform(BUFF_SPAWN_MIN, BUFF_SPAWN_MAX)
        # срок жизни
        self.buffs = [b for b in self.buffs if b.update(dt)]
        # подбор игроком
        for buff in self.buffs[:]:
            if buff.pos.distance_to(self.player.pos) < buff.radius + self.player.radius:
                self.buffs.remove(buff)
                self.player.apply_buff(buff)
                spawn_explosion(buff.pos.x, buff.pos.y, self.particles, buff.color, 14)
                Sounds.play("powerup")

    def spawn_buff(self):
        """Создаёт баф со случайным типом в случайной точке вдали от игрока."""
        kind = random.choices([k for k, _ in BUFF_WEIGHTS],
                              weights=[w for _, w in BUFF_WEIGHTS])[0]
        buff = Buff(kind)
        for _ in range(6):
            if buff.pos.distance_to(self.player.pos) > 140:
                break
            buff.pos = pygame.Vector2(random.uniform(70, WIDTH - 70),
                                      random.uniform(90, HEIGHT - 90))
        self.buffs.append(buff)

    # -------------------------------------------------------------- улучшения
    def start_upgrade_selection(self):
        """Босс убит — предлагаем выбрать одно из трёх улучшений."""
        self.upgrade_options = self.roll_upgrades()
        self.upgrade_rects = []
        self.state = "upgrading"

    def roll_upgrades(self):
        """Три разных улучшения; каждый слот с шансом становится редким."""
        commons = ["hp", "damage", "fire", "pierce", "speed"]
        rares = ["regen", "vampire"]
        random.shuffle(commons)
        options = []
        rare_pool = list(rares)
        for _ in range(3):
            if rare_pool and random.random() < RARE_CHANCE:
                options.append(rare_pool.pop(random.randrange(len(rare_pool))))
            else:
                options.append(commons.pop())
        return options

    def _choose_upgrade(self, index):
        if not (0 <= index < len(self.upgrade_options)):
            return
        kind = self.upgrade_options[index]
        self.player.apply_upgrade(kind)
        spawn_explosion(self.player.pos.x, self.player.pos.y,
                        self.particles, UPGRADES[kind]["color"], 24)
        Sounds.play("powerup")
        self.upgrade_options = []
        self.state = "playing"

    def draw_upgrade_screen(self):
        """Экран выбора улучшения после убийства босса."""
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 170))
        self.screen.blit(overlay, (0, 0))
        title = self.fonts["title"].render("ВЫБЕРИ УЛУЧШЕНИЕ", True, TEXT_COLOR)
        self.screen.blit(title, title.get_rect(center=(WIDTH // 2, 140)))
        sub = self.fonts["small"].render("Нажми 1, 2 или 3 — или кликни мышью",
                                         True, (170, 175, 190))
        self.screen.blit(sub, sub.get_rect(center=(WIDTH // 2, 190)))

        card_w, card_h, gap = 310, 210, 36
        total = card_w * 3 + gap * 2
        x0 = (WIDTH - total) // 2
        y0 = 250
        self.upgrade_rects = []
        for i, kind in enumerate(self.upgrade_options):
            data = UPGRADES[kind]
            rare = data["rarity"] == "rare"
            rect = pygame.Rect(x0 + i * (card_w + gap), y0, card_w, card_h)
            self.upgrade_rects.append(rect)
            bg = (36, 40, 50) if not rare else (46, 40, 32)
            pygame.draw.rect(self.screen, bg, rect, border_radius=14)
            border = (255, 215, 0) if rare else (95, 105, 125)
            pygame.draw.rect(self.screen, border, rect, 3, border_radius=14)
            num = self.fonts["big"].render(f"{i + 1}", True, (150, 155, 175))
            self.screen.blit(num, (rect.x + 14, rect.y + 10))
            if rare:
                badge = self.fonts["small"].render("РЕДКОЕ", True, (255, 215, 0))
                self.screen.blit(badge, (rect.right - badge.get_width() - 14,
                                         rect.y + 14))
            title_s = self.fonts["hud"].render(data["title"], True, data["color"])
            self.screen.blit(title_s, title_s.get_rect(center=(rect.centerx,
                                                               rect.y + 60)))
            lines = wrap_text(self.fonts["small"], data["desc"], card_w - 30)
            ty = rect.y + 100
            for line in lines:
                line_s = self.fonts["small"].render(line, True, (205, 210, 225))
                self.screen.blit(line_s, line_s.get_rect(center=(rect.centerx, ty)))
                ty += 26

    # -------------------------------------------------------------- отрисовка
    def draw(self):
        shake_x = random.uniform(-1, 1) * 6 * (self.shake > 0)
        shake_y = random.uniform(-1, 1) * 6 * (self.shake > 0)
        self.screen.fill(BG_COLOR)
        self.background.draw(self.screen, int(shake_x) if self.shake > 0 else 0)

        if self.state in ("playing", "paused", "gameover", "upgrading"):
            for p in self.particles:
                p.draw(self.screen)
            for b in self.bullets:
                b.draw(self.screen)
            for e in self.enemies:
                e.draw(self.screen)
            for buff in self.buffs:
                buff.draw(self.screen, self.fonts["hud"])
            self.player.draw(self.screen)
            draw_hud(self.screen, self.fonts, self.player,
                     self.score, self.waves.wave, self.kills)
            if self.state == "playing":
                self.waves.draw_boss_alert(self.screen, self.fonts["big"])

        if self.state == "menu":
            draw_center_message(
                self.screen, self.fonts,
                "2D ШУТЕР",
                "SPACE — начать игру\nWASD — движение, ЛКМ — огонь",
            )
            hints = [
                "Уничтожай врагов, переживи как можно больше волн.",
                "Собирай бафы: аптечка, скорострельность, ускорение, урон, щит.",
                "Победи босса — выбери одно из трёх улучшений!",
                "Каждые 5 волн появляется босс!",
            ]
            for i, hint in enumerate(hints):
                s = self.fonts["small"].render(hint, True, (150, 155, 175))
                self.screen.blit(s, s.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 60 + i * 30)))

        elif self.state == "paused":
            draw_center_message(self.screen, self.fonts,
                                "ПАУЗА", "ESC — продолжить, R — заново")

        elif self.state == "gameover":
            draw_center_message(
                self.screen, self.fonts,
                "ИГРА ОКОНЧЕНА",
                f"Счёт: {self.score}   |   Волна: {self.waves.wave}   |   Убито: {self.kills}",
            )
            hint = self.fonts["big"].render("R — сыграть ещё раз   ESC — в меню",
                                            True, (150, 155, 175))
            self.screen.blit(hint, hint.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 70)))

        elif self.state == "upgrading":
            self.draw_upgrade_screen()

        pygame.display.flip()

    # -------------------------------------------------------------- цикл
    def run(self):
        running = True
        while running:
            dt = self.clock.tick(FPS) / 1000.0
            running = self.handle_events()
            self.update(dt)
            self.draw()
        pygame.quit()


if __name__ == "__main__":
    Game().run()