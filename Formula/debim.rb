class Debim < Formula
  include Language::Python::Virtualenv

  desc "Minimal Git-native Declarative BIM engine & MCP Server for AI agents and humans"
  homepage "https://github.com/PRIDA-TAKON/debim"
  url "https://github.com/PRIDA-TAKON/debim/archive/refs/tags/v0.3.0.tar.gz"
  sha256 "735377f2d34a6b457bc2713b0a050033f048e5fd6cf26703a22f8c885b50fdea"
  license "MIT"

  depends_on "python@3.11"

  def install
    venv = virtualenv_create(libexec, "python3.11")
    venv.pip_install "debim[all]==#{version}"
    bin.install_symlink libexec/"bin/debim"
    bin.install_symlink libexec/"bin/bim"
  end

  test do
    assert_match "debim version", shell_output("#{bin}/debim --version")
  end
end
