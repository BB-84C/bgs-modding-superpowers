#pragma once

#include <string>
#include <vector>

namespace mo2::control_plane {

enum class CommandSafetyLevel {
  SafeRead,
  ControlledWrite,
  DangerousWrite,
};

struct RegisteredCommand {
  std::string name;
  CommandSafetyLevel safetyLevel;
};

class CommandRegistry {
 public:
  CommandRegistry();
  const std::vector<RegisteredCommand>& commands() const;

 private:
  std::vector<RegisteredCommand> commands_;
};

}  // namespace mo2::control_plane
