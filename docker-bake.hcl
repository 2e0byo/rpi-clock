variable "REPO" {
  default = "2e0byo"
}

variable "VERSION" {
}

target "_setup" {
  platforms = ["linux/amd64", "linux/arm64"]
  cache-to = [
    "type=gha,mode=max"
  ]
  cache-from = [
    "type=gha"
  ]
}

target "rpi-clock" {
  tags = [
    "${REPO}/rpi-clock:latest",
    "${REPO}/rpi-clock:${VERSION}",
  ]
  inherits = ["_setup"]
}


group "default" {
  targets = ["rpi-clock"]
}
