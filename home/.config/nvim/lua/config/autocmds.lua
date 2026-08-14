-- Briefly show what was copied.
local highlight_group = vim.api.nvim_create_augroup("YankHighlight", { clear = true })
vim.api.nvim_create_autocmd("TextYankPost", {
  group = highlight_group,
  callback = function()
    vim.highlight.on_yank({ timeout = 150 })
  end,
})

-- Enable inlay hints whenever an LSP client attaches.
local inlay_group = vim.api.nvim_create_augroup("InlayHints", { clear = true })
vim.api.nvim_create_autocmd("LspAttach", {
  group = inlay_group,
  callback = function(event)
    vim.lsp.inlay_hint.enable(true, { bufnr = event.buf })
  end,
})

-- Automatically show the diagnostic float for the current line on hover.
local diag_float_group = vim.api.nvim_create_augroup("DiagnosticFloat", { clear = true })
vim.api.nvim_create_autocmd("CursorHold", {
  group = diag_float_group,
  callback = function(event)
    -- Only open a float if the cursor line actually has a diagnostic.
    local diagnostics = vim.diagnostic.get(event.buf, { lnum = vim.fn.line(".") - 1 })
    if #diagnostics > 0 then
      vim.diagnostic.open_float(nil, {
        bufnr = event.buf,
        scope = "cursor",
        focusable = false,
        close_events = { "CursorMoved", "InsertEnter", "BufLeave" },
      })
    end
  end,
})
