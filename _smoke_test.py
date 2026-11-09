import os

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame

import main

# чистый старт без сохранённых рекордов
try:
    os.remove(main.HIGHSCORE_FILE)
except OSError:
    pass

g = main.Game()
assert (g.best_score, g.best_kills) == (0, 0)
g.draw()  # меню с рекордом

# старт игры
pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE))
g.handle_events()
assert g.state == "playing"
g.waves.spawn_timer = 99999
g.buff_spawn_timer = 99999
for _ in range(60):
    g.update(1 / 60)
    g.draw()

# пауза по ESC; мир заморожен
pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
g.handle_events()
assert g.state == "paused", g.state
n = len(g.enemies)
for _ in range(30):
    g.update(1 / 60)
assert len(g.enemies) == n and g.player.hp == g.player.hp
g.draw()
print("pause ESC + world frozen OK")

# SPACE — продолжить
pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE))
g.handle_events()
assert g.state == "playing"

# R на паузе — рестарт с нуля
pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
g.handle_events()
g.score = 999
pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_r))
g.handle_events()
assert g.state == "playing" and g.score == 0 and g.player.hp == 100
print("pause R restart OK")

# Q на паузе — в меню
pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
g.handle_events()
assert g.state == "paused"
pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_q))
g.handle_events()
assert g.state == "menu"
print("pause Q menu OK")

# P — альтернатива ESC
pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE))
g.handle_events()
pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_p))
g.handle_events()
assert g.state == "paused"
pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_p))
g.handle_events()
assert g.state == "playing"
print("P toggle OK")

# рекорд: проигрыш с очками -> сохранение + экран "НОВЫЙ РЕКОРД"
g2 = main.Game()
g2.reset()
g2.state = "playing"
g2.score = 77
g2.kills = 5
g2.player.alive = False
g2._save_highscore()
g2.draw()
assert g2.best_score == 77 and g2.best_kills == 5
assert g2.new_record is True
print("highscore save OK, new_record =", g2.new_record)

# новый экземпляр игры подхватывает рекорд из файла
g3 = main.Game()
assert (g3.best_score, g3.best_kills) == (77, 5), (g3.best_score, g3.best_kills)
g3.draw()
print("highscore load OK")

# повторный проигрыш с меньшим счётом — рекорд не трогается
g4 = main.Game()
g4.reset()
g4.state = "playing"
g4.score = 20
g4.kills = 1
g4.player.alive = False
g4._save_highscore()
assert g4.new_record is False and g4.best_score == 77
print("no false record OK")

try:
    os.remove(main.HIGHSCORE_FILE)
except OSError:
    pass

print("ALL OK")