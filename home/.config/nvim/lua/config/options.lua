local opt = vim.opt

-- Editing
opt.number = true
opt.relativenumber = true
opt.clipboard = "unnamedplus"
opt.undofile = true
opt.ignorecase = true
opt.smartcase = true
opt.incsearch = true
opt.hlsearch = true
opt.wrap = false
opt.scrolloff = 6
opt.sidescrolloff = 8
opt.splitright = true
opt.splitbelow = true

-- Indentation
opt.expandtab = true
opt.tabstop = 4
opt.shiftwidth = 4
opt.smartindent = true

-- Appearance and feedback
opt.termguicolors = true
opt.signcolumn = "yes"
opt.colorcolumn = "80,120"
opt.cursorline = true
opt.updatetime = 250
opt.timeoutlen = 300
opt.completeopt = { "menuone", "noselect" }

opt.fillchars = {
  vert = "┃",
  horiz = "━",
  verthoriz = "╋",
  vertleft = "┫",
  vertright = "┣",
  horizup = "┻",
  horizdown = "┳",
}

local function set_separator_highlight()
  vim.api.nvim_set_hl(0, "WinSeparator", {
    fg = "#89b4fa",
    bold = true,
  })
end

set_separator_highlight()
vim.api.nvim_create_autocmd("ColorScheme", {
  callback = set_separator_highlight,
})
