import os

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame

import main

# тестовые файлы, чтобы не трогать реальные рекорды/настройки игрока
main.HIGHSCORE_FILE = "_test_highscore.json"
main.SETTINGS_FILE = "_test_settings.json"


def cleanup():
    for f in (main.HIGHSCORE_FILE, main.SETTINGS_FILE):
        try:
            os.remove(f)
        except OSError:
            pass


cleanup()

# ---------------------------------------------------------------- настройки фона
g = main.Game()
assert g.background.kind == "grid", g.background.kind
g.draw()  # меню

# S открывает настройки
pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_s))
g.handle_events()
assert g.state == "settings", g.state
g.draw()  # экран настроек с превью

# RIGHT -> асфальт, сохранение в файл
pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RIGHT))
g.handle_events()
assert g.background.kind == "asphalt"
assert main.load_background_kind() == "asphalt"
g.draw()
print("settings RIGHT -> asphalt OK, saved")

# новый экземпляр подхватывает сохранённый фон
g2 = main.Game()
assert g2.background.kind == "asphalt"
print("settings load on startup OK")

# LEFT -> сетка
pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_LEFT))
g.handle_events()
assert g.background.kind == "grid"
# 2 -> асфальт, 3 -> поляна, 1 -> сетка
pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_2))
g.handle_events()
assert g.background.kind == "asphalt"
pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_3))
g.handle_events()
assert g.background.kind == "meadow"
g.draw()  # экран настроек с тремя карточками
assert main.load_background_kind() == "meadow"
pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_1))
g.handle_events()
assert g.background.kind == "grid"
# ESC -> в меню
pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
g.handle_events()
assert g.state == "menu"
print("settings LEFT/1/2/ESC OK")

# игра на фоне "поляна" работает
g2._set_background("meadow")
g2.reset()
g2.state = "playing"
g2.waves.spawn_timer = 99999
g2.buff_spawn_timer = 99999
for _ in range(30):
    g2.update(1 / 60)
    g2.draw()
print("gameplay on meadow OK")
g2._set_background("grid")
g2.reset()
g2.state = "playing"
g2.waves.spawn_timer = 99999
g2.buff_spawn_timer = 99999
for _ in range(30):
    g2.update(1 / 60)
    g2.draw()
print("gameplay on asphalt OK")

# ---------------------------------------------------------------- пауза
pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
g2.handle_events()
assert g2.state == "paused", g2.state
n = len(g2.enemies)
for _ in range(30):
    g2.update(1 / 60)
assert len(g2.enemies) == n
g2.draw()
pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE))
g2.handle_events()
assert g2.state == "playing"
# R на паузе — рестарт
pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
g2.handle_events()
g2.score = 999
pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_r))
g2.handle_events()
assert g2.state == "playing" and g2.score == 0 and g2.player.hp == 100
# Q на паузе — меню
pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
g2.handle_events()
pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_q))
g2.handle_events()
assert g2.state == "menu"
# P — пауза
pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE))
g2.handle_events()
pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_p))
g2.handle_events()
assert g2.state == "paused"
pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_p))
g2.handle_events()
assert g2.state == "playing"
print("pause ESC/SPACE/R/Q/P OK")

# ---------------------------------------------------------------- рекорд
g3 = main.Game()
g3.reset()
g3.state = "playing"
g3.score = 77
g3.kills = 5
g3.player.alive = False
g3._save_highscore()
assert g3.best_score == 77 and g3.best_kills == 5 and g3.new_record
g3.draw()  # экран gameover с "НОВЫЙ РЕКОРД!"

g4 = main.Game()
assert (g4.best_score, g4.best_kills) == (77, 5)
g4.reset()
g4.state = "playing"
g4.score = 20
g4.kills = 1
g4.player.alive = False
g4._save_highscore()
assert g4.new_record is False and g4.best_score == 77
g4.draw()
print("highscore save/load OK")

# --------------------------------------------------------- пробитие (регрессия)
g5 = main.Game()
g5.reset()
g5.state = "playing"
g5.waves.spawn_timer = 99999
g5.buff_spawn_timer = 99999
e1 = main.Enemy("basic")
e1.pos = g5.player.pos + pygame.Vector2(120, 0)
e2 = main.Enemy("basic")
e2.pos = g5.player.pos + pygame.Vector2(420, 0)
g5.enemies = [e1, e2]
g5.bullets = [main.Bullet(g5.player.pos.x + 60, g5.player.pos.y,
                          pygame.Vector2(850, 0), 25, 5, main.BULLET_COLOR,
                          pierce=1)]
for _ in range(60):
    g5.update(1 / 60)
assert e1.hp == 15 and e2.hp == 15 and g5.kills == 0, (e1.hp, e2.hp, g5.kills)
print("pierce: 25 damage each, no double-hit OK")

cleanup()
print("ALL OK")