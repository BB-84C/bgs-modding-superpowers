#pragma once

#include "CommandRegistry.h"

namespace mo2::control_plane {

class Mo2AgentControlPlugin {
 public:
  Mo2AgentControlPlugin();

  const CommandRegistry& registry() const;

 private:
  CommandRegistry registry_;
};

}  // namespace mo2::control_plane
