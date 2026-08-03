cmake_minimum_required(VERSION 3.13)

# In your own repo, point this include at the kit submodule, for
# example kit/firmware/kit.cmake.
include(../kit.cmake)

project(blink_example C CXX ASM)
set(CMAKE_C_STANDARD 11)

pico_sdk_init()

tt_extension(tt_host blink_ext.c)
