#pragma once

#include <string>

namespace mo2::control_plane {

struct RequestEnvelope {
  std::string protocolVersion{"1"};
  std::string requestId;
  std::string sessionId;
  std::string command;
};

struct ResponseEnvelope {
  std::string protocolVersion{"1"};
  std::string requestId;
  std::string sessionId;
  bool ok{false};
};

}  // namespace mo2::control_plane
