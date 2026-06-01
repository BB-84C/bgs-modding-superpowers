#include "CommandRegistry.h"

namespace mo2::control_plane {

namespace {

std::vector<RegisteredCommand> BuildFoundationCommands() {
  return {
      {"system.ping", CommandSafetyLevel::SafeRead},
      {"system.capabilities", CommandSafetyLevel::SafeRead},
      {"system.status", CommandSafetyLevel::SafeRead},
  };
}

std::vector<RegisteredCommand> BuildPrimitiveCommands() {
  return {
      {"profile.list", CommandSafetyLevel::SafeRead},
      {"profile.get-current", CommandSafetyLevel::SafeRead},
      {"profile.set-current", CommandSafetyLevel::ControlledWrite},
      {"executables.list", CommandSafetyLevel::SafeRead},
      {"executables.get", CommandSafetyLevel::SafeRead},
      {"mods.list", CommandSafetyLevel::SafeRead},
      {"plugins.list", CommandSafetyLevel::SafeRead},
      {"organizer.refresh", CommandSafetyLevel::ControlledWrite},
      {"launch.start", CommandSafetyLevel::ControlledWrite},
      {"launch.status", CommandSafetyLevel::SafeRead},
      {"launch.wait", CommandSafetyLevel::SafeRead},
      {"launch.stop", CommandSafetyLevel::ControlledWrite},
  };
}

std::vector<RegisteredCommand> BuildCommands() {
  auto commands = BuildFoundationCommands();
  auto primitiveCommands = BuildPrimitiveCommands();
  commands.insert(commands.end(), primitiveCommands.begin(), primitiveCommands.end());
  return commands;
}

}  // namespace

CommandRegistry::CommandRegistry() : commands_(BuildCommands()) {}

const std::vector<RegisteredCommand>& CommandRegistry::commands() const {
  return commands_;
}

}  // namespace mo2::control_plane
