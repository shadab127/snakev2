"""Shared fixtures for SnakeV2 tests."""
import os
import sys

import pytest

# --- Headless pygame init -------------------------------------------------
# Must happen before any module imports pygame.
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame


@pytest.fixture(scope="session", autouse=True)
def pygame_headless():
    """Initialise pygame in headless/dummy mode once per session.
    Does not call set_mode — SnakeGame.__init__ does that on its own
    with the dummy video driver.
    """
    if not pygame.display.get_init():
        pygame.display.init()
    if not pygame.font.get_init():
        pygame.font.init()
    yield


@pytest.fixture(autouse=True)
def reset_pygame_modules():
    """Re-initialise modules that get implicitly quit by some backends."""
    yield
    # keep the display module alive across tests
    if pygame.display.get_init():
        pygame.display.quit()
