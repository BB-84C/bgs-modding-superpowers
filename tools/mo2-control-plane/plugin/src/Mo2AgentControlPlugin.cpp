#include "Mo2AgentControlPlugin.h"

namespace mo2::control_plane {

Mo2AgentControlPlugin::Mo2AgentControlPlugin() = default;

const CommandRegistry& Mo2AgentControlPlugin::registry() const {
  return registry_;
}

}  // namespace mo2::control_plane
