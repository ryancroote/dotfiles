local map = vim.keymap.set

-- Configure how diagnostics are displayed.
vim.diagnostic.config({
  virtual_text = true,
  signs = true,
  underline = true,
  update_in_insert = false,
  severity_sort = true,
  float = {
    source = "if_many",
    border = "rounded",
    header = "",
    prefix = "",
  },
})

-- All custom keymaps are routed through <leader> so they are consistently
-- discoverable via which-key.nvim. Namespaces used below:
--   <leader>g  LSP (goto / refactoring / symbols)
--   <leader>d  diagnostics
--   <leader>s  git (source control)
--   <leader>h  gitsigns hunk (defined in plugins/init.lua)

-- General mappings.
map("n", "<leader><Esc>", "<cmd>nohlsearch<CR>", { silent = true, desc = "Clear search highlight" })
map("n", "<leader>w", "<cmd>write<CR>", { silent = true, desc = "Write file" })
map("n", "<leader>x", "<cmd>quit<CR>", { silent = true, desc = "Quit window" })
map("n", "<leader>e", "<cmd>NvimTreeToggle<CR>", { silent = true, desc = "Toggle file explorer" })

-- Diagnostic navigation and listings.
map("n", "<leader>dn", vim.diagnostic.goto_next, { silent = true, desc = "Next diagnostic" })
map("n", "<leader>dN", vim.diagnostic.goto_prev, { silent = true, desc = "Previous diagnostic" })
map("n", "<leader>df", vim.diagnostic.open_float, { silent = true, desc = "Show diagnostic float" })

-- LSP mappings are available only when an LSP client attaches.
local lsp_group = vim.api.nvim_create_augroup("LspKeymaps", { clear = true })
vim.api.nvim_create_autocmd("LspAttach", {
  group = lsp_group,
  callback = function(event)
    local function lsp_opts(desc)
      return { buffer = event.buf, silent = true, desc = desc }
    end

    local telescope = require("telescope.builtin")

    -- Navigation.
    map("n", "<leader>gd", telescope.lsp_definitions, lsp_opts("Goto definition"))
    map("n", "<leader>gD", vim.lsp.buf.declaration, lsp_opts("Goto declaration"))
    map("n", "<leader>gR", telescope.lsp_references, lsp_opts("Goto references"))
    map("n", "<leader>gi", telescope.lsp_implementations, lsp_opts("Goto implementation"))

    -- Info.
    map("n", "<leader>gh", vim.lsp.buf.hover, lsp_opts("Hover documentation"))
    map("n", "<leader>gk", vim.lsp.buf.signature_help, lsp_opts("Signature help"))

    -- Refactoring.
    map({ "n", "v" }, "<leader>ga", vim.lsp.buf.code_action, lsp_opts("Code action"))
    map("n", "<leader>gr", vim.lsp.buf.rename, lsp_opts("Rename symbol"))

    -- Symbols.
    map("n", "<leader>gs", telescope.lsp_document_symbols, lsp_opts("Document symbols"))
    map("n", "<leader>gS", telescope.lsp_dynamic_workspace_symbols, lsp_opts("Workspace symbols"))

    -- Diagnostics listings (under the <leader>d namespace for consistency).
    map("n", "<leader>dd", function()
      telescope.diagnostics({ bufnr = event.buf })
    end, lsp_opts("Document diagnostics"))
    map("n", "<leader>dw", telescope.diagnostics, lsp_opts("Workspace diagnostics"))
  end,
})