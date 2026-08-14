return {
  {
    "catppuccin/nvim",
    name = "catppuccin",
    priority = 1000,
    config = function()
      require("catppuccin").setup({
        flavour = "mocha",
        auto_integrations = true,
      })
      vim.cmd.colorscheme("catppuccin-mocha")
    end,
  },
  {
    "folke/which-key.nvim",
    event = "VeryLazy",
    opts = {},
    keys = {
      {
        "<leader>?",
        function()
          require("which-key").show()
        end,
        desc = "Show keymaps",
      },
    },
  },
  {
    "nvim-tree/nvim-tree.lua",
    dependencies = { "nvim-tree/nvim-web-devicons" },
    cmd = { "NvimTreeOpen", "NvimTreeToggle", "NvimTreeFindFile" },
    opts = {},
  },
  { "mason-org/mason.nvim", opts = {} },
  {
    "mason-org/mason-lspconfig.nvim",
    dependencies = { "mason-org/mason.nvim", "neovim/nvim-lspconfig" },
    opts = {
      ensure_installed = { "pyrefly" },
    },
  },
  {
    "neovim/nvim-lspconfig",
    config = function()
      vim.lsp.enable("pyrefly")
    end,
  },
  {
    "saghen/blink.cmp",
    version = "1.*",
    dependencies = { "rafamadriz/friendly-snippets" },
    opts = {
      keymap = { preset = "default" },
      sources = {
        default = { "lsp", "path", "snippets", "buffer" },
      },
      signature = { enabled = true },
    },
  },
  {
    "nvim-telescope/telescope.nvim",
    dependencies = { "nvim-lua/plenary.nvim" },
    keys = {
      { "<leader>ff", "<cmd>Telescope find_files<CR>", desc = "Find files" },
      {
        "<leader>sf",
        function()
          local git_root = vim.fn.system({ "git", "rev-parse", "--show-toplevel" })
          if vim.v.shell_error == 0 then
            require("telescope.builtin").git_files()
          else
            require("telescope.builtin").find_files()
          end
        end,
        desc = "Find git files",
      },
      { "<leader>fg", "<cmd>Telescope live_grep<CR>", desc = "Live grep" },
      { "<leader>fb", "<cmd>Telescope buffers<CR>", desc = "Find buffers" },
    },
  },
  {
    "sindrets/diffview.nvim",
    cmd = { "DiffviewOpen", "DiffviewFileHistory", "DiffviewClose" },
    keys = {
      { "<leader>sd", "<cmd>DiffviewOpen<CR>", desc = "Open diff view" },
    },
    opts = {
      view = {
        merge_tool = {
          layout = "diff1_plain",
        },
      },
    },
  },
  {
    "lewis6991/gitsigns.nvim",
    opts = {
      current_line_blame = false,
      on_attach = function(bufnr)
        local gitsigns = package.loaded.gitsigns
        local function map(lhs, rhs, desc)
          vim.keymap.set("n", lhs, rhs, { buffer = bufnr, silent = true, desc = desc })
        end
        local function visual_hunk(action)
          return function()
            local start = vim.fn.line(".")
            local finish = vim.fn.line("v")
            action({ math.min(start, finish), math.max(start, finish) })
          end
        end

        map("<leader>hn", gitsigns.next_hunk, "Next hunk")
        map("<leader>hN", gitsigns.prev_hunk, "Previous hunk")
        map("<leader>hs", gitsigns.stage_hunk, "Stage hunk")
        map("<leader>hr", gitsigns.reset_hunk, "Reset hunk")
        map("<leader>hp", gitsigns.preview_hunk, "Preview hunk")
        map("<leader>hb", gitsigns.toggle_current_line_blame, "Toggle line blame")
        vim.keymap.set("v", "<leader>hs", visual_hunk(gitsigns.stage_hunk), {
          buffer = bufnr,
          silent = true,
          desc = "Stage selected hunk",
        })
        vim.keymap.set("v", "<leader>hr", visual_hunk(gitsigns.reset_hunk), {
          buffer = bufnr,
          silent = true,
          desc = "Reset selected hunk",
        })
      end,
    },
  },
  {
    "NeogitOrg/neogit",
    dependencies = { "nvim-telescope/telescope.nvim" },
    cmd = "Neogit",
    keys = {
      { "<leader>ss", "<cmd>Neogit<CR>", desc = "Git status" },
    },
    opts = {},
  },
  {
    "nvim-treesitter/nvim-treesitter",
    branch = "master",
    lazy = false,
    build = ":TSUpdate",
    config = function()
      local languages = { "bash", "json", "lua", "markdown", "python", "vim", "vimdoc", "yaml" }
      local treesitter = require("nvim-treesitter")

      treesitter.setup({
        install_dir = vim.fn.stdpath("data") .. "/site",
      })
      treesitter.install(languages)

      vim.api.nvim_create_autocmd("FileType", {
        pattern = languages,
        callback = function()
          pcall(vim.treesitter.start)
        end,
      })
    end,
  },
}
