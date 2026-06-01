cmake_minimum_required(VERSION 3.21)

project(Mo2AgentControlPlugin LANGUAGES CXX)

add_library(Mo2AgentControlPlugin STATIC
  src/Mo2AgentControlPlugin.cpp
  src/CommandRegistry.cpp
)

target_include_directories(Mo2AgentControlPlugin
  PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}/src
)

target_compile_features(Mo2AgentControlPlugin PUBLIC cxx_std_17)
