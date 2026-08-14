-- Bootstrap lazy.nvim, which manages the plugins below.
local lazypath = vim.fn.stdpath("data") .. "/lazy/lazy.nvim"
if not vim.uv.fs_stat(lazypath) then
  local output = vim.fn.system({
    "git",
    "clone",
    "--filter=blob:none",
    "https://github.com/folke/lazy.nvim.git",
    "--branch=stable",
    lazypath,
  })
  if vim.v.shell_error ~= 0 then
    error("Unable to install lazy.nvim:\n" .. output)
  end
end
vim.opt.rtp:prepend(lazypath)

require("lazy").setup(require("plugins"))
