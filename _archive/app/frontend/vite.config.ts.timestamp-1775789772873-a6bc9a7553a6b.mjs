// vite.config.ts
import { defineConfig } from "file:///workspace/app/frontend/node_modules/.pnpm/vite@5.4.21_@types+node@22.19.7/node_modules/vite/dist/node/index.js";
import react from "file:///workspace/app/frontend/node_modules/.pnpm/@vitejs+plugin-react-swc@3.11.0_vite@5.4.21/node_modules/@vitejs/plugin-react-swc/index.js";
import path from "path";
import { viteSourceLocator } from "file:///workspace/app/frontend/node_modules/.pnpm/@metagptx+vite-plugin-source-locator@0.0.14_rollup@2.79.2_vite@5.4.21/node_modules/@metagptx/vite-plugin-source-locator/dist/index.mjs";
import { atoms } from "file:///workspace/app/frontend/node_modules/.pnpm/@metagptx+web-sdk@0.0.68_eslint@9.39.2_prettier@3.8.1_vite@5.4.21/node_modules/@metagptx/web-sdk/dist/plugins.js";
var __vite_injected_original_dirname = "/workspace/app/frontend";
process.env.VITE_APP_TITLE ??= process.env.OVERVIEW_TITLE ?? "AlignX - AI Agent\u9A71\u52A8\u7684\u4E9A\u9A6C\u900A\u5356\u5BB6\u8FD0\u8425\u4E2D\u67A2";
process.env.VITE_APP_DESCRIPTION ??= process.env.OVERVIEW_DESCRIPTION ?? "AlignX\u901A\u8FC7CosmoAI\u8BED\u4E49\u7FFB\u8BD1\u5668\u548CProfitPilot\u5E7F\u544A\u4F18\u5316\u5E08\uFF0C\u5E2E\u52A9\u4E9A\u9A6C\u900AFBA\u5356\u5BB6\u5728Cosmo\u7B97\u6CD5\u65F6\u4EE3\u5B9E\u73B0\u6D41\u91CF\u6062\u590D\u548C\u5229\u6DA6\u589E\u957F";
process.env.VITE_APP_LOGO_URL ??= process.env.OVERVIEW_LOGO_URL ?? "https://public-frontend-cos.metadl.com/mgx/img/favicon_atoms.ico";
var vite_config_default = defineConfig(({ mode }) => ({
  plugins: [
    viteSourceLocator({
      prefix: "mgx"
      // 前缀用于标识源代码位置，不能修改
    }),
    react(),
    atoms()
  ],
  resolve: {
    alias: {
      "@": path.resolve(__vite_injected_original_dirname, "./src")
    }
  },
  server: {
    host: "0.0.0.0",
    // 监听所有网络接口
    port: parseInt(process.env.VITE_PORT || "3000"),
    proxy: {
      "/api": {
        target: `http://localhost:8003`,
        changeOrigin: true,
        timeout: 12e4,
        proxyTimeout: 12e4
      }
    },
    watch: { usePolling: true, interval: 600 }
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          // Vendor chunks
          "react-vendor": ["react", "react-dom"],
          "router-vendor": ["react-router-dom"],
          "ui-vendor": [
            "@radix-ui/react-accordion",
            "@radix-ui/react-alert-dialog",
            "@radix-ui/react-aspect-ratio",
            "@radix-ui/react-avatar",
            "@radix-ui/react-checkbox",
            "@radix-ui/react-collapsible",
            "@radix-ui/react-context-menu",
            "@radix-ui/react-dialog",
            "@radix-ui/react-dropdown-menu",
            "@radix-ui/react-hover-card",
            "@radix-ui/react-label",
            "@radix-ui/react-menubar",
            "@radix-ui/react-navigation-menu",
            "@radix-ui/react-popover",
            "@radix-ui/react-progress",
            "@radix-ui/react-radio-group",
            "@radix-ui/react-scroll-area",
            "@radix-ui/react-select",
            "@radix-ui/react-separator",
            "@radix-ui/react-slider",
            "@radix-ui/react-slot",
            "@radix-ui/react-switch",
            "@radix-ui/react-tabs",
            "@radix-ui/react-toast",
            "@radix-ui/react-toggle",
            "@radix-ui/react-toggle-group",
            "@radix-ui/react-tooltip"
          ],
          "form-vendor": ["react-hook-form", "@hookform/resolvers", "zod"],
          "utils-vendor": [
            "axios",
            "clsx",
            "tailwind-merge",
            "class-variance-authority",
            "date-fns",
            "lucide-react"
          ],
          "query-vendor": ["@tanstack/react-query"]
        }
      }
    },
    chunkSizeWarningLimit: 1e3
  }
}));
export {
  vite_config_default as default
};
//# sourceMappingURL=data:application/json;base64,ewogICJ2ZXJzaW9uIjogMywKICAic291cmNlcyI6IFsidml0ZS5jb25maWcudHMiXSwKICAic291cmNlc0NvbnRlbnQiOiBbImNvbnN0IF9fdml0ZV9pbmplY3RlZF9vcmlnaW5hbF9kaXJuYW1lID0gXCIvd29ya3NwYWNlL2FwcC9mcm9udGVuZFwiO2NvbnN0IF9fdml0ZV9pbmplY3RlZF9vcmlnaW5hbF9maWxlbmFtZSA9IFwiL3dvcmtzcGFjZS9hcHAvZnJvbnRlbmQvdml0ZS5jb25maWcudHNcIjtjb25zdCBfX3ZpdGVfaW5qZWN0ZWRfb3JpZ2luYWxfaW1wb3J0X21ldGFfdXJsID0gXCJmaWxlOi8vL3dvcmtzcGFjZS9hcHAvZnJvbnRlbmQvdml0ZS5jb25maWcudHNcIjtpbXBvcnQgeyBkZWZpbmVDb25maWcgfSBmcm9tICd2aXRlJztcbmltcG9ydCByZWFjdCBmcm9tICdAdml0ZWpzL3BsdWdpbi1yZWFjdC1zd2MnO1xuaW1wb3J0IHBhdGggZnJvbSAncGF0aCc7XG5pbXBvcnQgeyB2aXRlU291cmNlTG9jYXRvciB9IGZyb20gJ0BtZXRhZ3B0eC92aXRlLXBsdWdpbi1zb3VyY2UtbG9jYXRvcic7XG5pbXBvcnQgeyBhdG9tcyB9IGZyb20gJ0BtZXRhZ3B0eC93ZWItc2RrL3BsdWdpbnMnO1xuXG5wcm9jZXNzLmVudi5WSVRFX0FQUF9USVRMRSA/Pz0gcHJvY2Vzcy5lbnYuT1ZFUlZJRVdfVElUTEUgPz8gJ0FsaWduWCAtIEFJIEFnZW50XHU5QTcxXHU1MkE4XHU3Njg0XHU0RTlBXHU5QTZDXHU5MDBBXHU1MzU2XHU1QkI2XHU4RkQwXHU4NDI1XHU0RTJEXHU2N0EyJztcbnByb2Nlc3MuZW52LlZJVEVfQVBQX0RFU0NSSVBUSU9OID8/PSBwcm9jZXNzLmVudi5PVkVSVklFV19ERVNDUklQVElPTiA/PyAnQWxpZ25YXHU5MDFBXHU4RkM3Q29zbW9BSVx1OEJFRFx1NEU0OVx1N0ZGQlx1OEJEMVx1NTY2OFx1NTQ4Q1Byb2ZpdFBpbG90XHU1RTdGXHU1NDRBXHU0RjE4XHU1MzE2XHU1RTA4XHVGRjBDXHU1RTJFXHU1MkE5XHU0RTlBXHU5QTZDXHU5MDBBRkJBXHU1MzU2XHU1QkI2XHU1NzI4Q29zbW9cdTdCOTdcdTZDRDVcdTY1RjZcdTRFRTNcdTVCOUVcdTczQjBcdTZENDFcdTkxQ0ZcdTYwNjJcdTU5MERcdTU0OENcdTUyMjlcdTZEQTZcdTU4OUVcdTk1N0YnO1xucHJvY2Vzcy5lbnYuVklURV9BUFBfTE9HT19VUkwgPz89IHByb2Nlc3MuZW52Lk9WRVJWSUVXX0xPR09fVVJMID8/ICdodHRwczovL3B1YmxpYy1mcm9udGVuZC1jb3MubWV0YWRsLmNvbS9tZ3gvaW1nL2Zhdmljb25fYXRvbXMuaWNvJztcblxuLy8gaHR0cHM6Ly92aXRlanMuZGV2L2NvbmZpZy9cbmV4cG9ydCBkZWZhdWx0IGRlZmluZUNvbmZpZygoeyBtb2RlIH0pID0+ICh7XG4gIHBsdWdpbnM6IFtcbiAgICB2aXRlU291cmNlTG9jYXRvcih7XG4gICAgICBwcmVmaXg6ICdtZ3gnLCAvLyBcdTUyNERcdTdGMDBcdTc1MjhcdTRFOEVcdTY4MDdcdThCQzZcdTZFOTBcdTRFRTNcdTc4MDFcdTRGNERcdTdGNkVcdUZGMENcdTRFMERcdTgwRkRcdTRGRUVcdTY1MzlcbiAgICB9KSxcbiAgICByZWFjdCgpLFxuICAgIGF0b21zKCksXG4gIF0sXG4gIHJlc29sdmU6IHtcbiAgICBhbGlhczoge1xuICAgICAgJ0AnOiBwYXRoLnJlc29sdmUoX19kaXJuYW1lLCAnLi9zcmMnKSxcbiAgICB9LFxuICB9LFxuICBzZXJ2ZXI6IHtcbiAgICBob3N0OiAnMC4wLjAuMCcsIC8vIFx1NzZEMVx1NTQyQ1x1NjI0MFx1NjcwOVx1N0Y1MVx1N0VEQ1x1NjNBNVx1NTNFM1xuICAgIHBvcnQ6IHBhcnNlSW50KHByb2Nlc3MuZW52LlZJVEVfUE9SVCB8fCAnMzAwMCcpLFxuICAgIHByb3h5OiB7XG4gICAgICAnL2FwaSc6IHtcbiAgICAgICAgdGFyZ2V0OiBgaHR0cDovL2xvY2FsaG9zdDo4MDAzYCxcbiAgICAgICAgY2hhbmdlT3JpZ2luOiB0cnVlLFxuICAgICAgICB0aW1lb3V0OiAxMjAwMDAsXG4gICAgICAgIHByb3h5VGltZW91dDogMTIwMDAwLFxuICAgICAgfSxcbiAgICB9LFxuICAgIHdhdGNoOiB7IHVzZVBvbGxpbmc6IHRydWUsIGludGVydmFsOiA2MDAgfSxcbiAgfSxcbiAgYnVpbGQ6IHtcbiAgICByb2xsdXBPcHRpb25zOiB7XG4gICAgICBvdXRwdXQ6IHtcbiAgICAgICAgbWFudWFsQ2h1bmtzOiB7XG4gICAgICAgICAgLy8gVmVuZG9yIGNodW5rc1xuICAgICAgICAgICdyZWFjdC12ZW5kb3InOiBbJ3JlYWN0JywgJ3JlYWN0LWRvbSddLFxuICAgICAgICAgICdyb3V0ZXItdmVuZG9yJzogWydyZWFjdC1yb3V0ZXItZG9tJ10sXG4gICAgICAgICAgJ3VpLXZlbmRvcic6IFtcbiAgICAgICAgICAgICdAcmFkaXgtdWkvcmVhY3QtYWNjb3JkaW9uJyxcbiAgICAgICAgICAgICdAcmFkaXgtdWkvcmVhY3QtYWxlcnQtZGlhbG9nJyxcbiAgICAgICAgICAgICdAcmFkaXgtdWkvcmVhY3QtYXNwZWN0LXJhdGlvJyxcbiAgICAgICAgICAgICdAcmFkaXgtdWkvcmVhY3QtYXZhdGFyJyxcbiAgICAgICAgICAgICdAcmFkaXgtdWkvcmVhY3QtY2hlY2tib3gnLFxuICAgICAgICAgICAgJ0ByYWRpeC11aS9yZWFjdC1jb2xsYXBzaWJsZScsXG4gICAgICAgICAgICAnQHJhZGl4LXVpL3JlYWN0LWNvbnRleHQtbWVudScsXG4gICAgICAgICAgICAnQHJhZGl4LXVpL3JlYWN0LWRpYWxvZycsXG4gICAgICAgICAgICAnQHJhZGl4LXVpL3JlYWN0LWRyb3Bkb3duLW1lbnUnLFxuICAgICAgICAgICAgJ0ByYWRpeC11aS9yZWFjdC1ob3Zlci1jYXJkJyxcbiAgICAgICAgICAgICdAcmFkaXgtdWkvcmVhY3QtbGFiZWwnLFxuICAgICAgICAgICAgJ0ByYWRpeC11aS9yZWFjdC1tZW51YmFyJyxcbiAgICAgICAgICAgICdAcmFkaXgtdWkvcmVhY3QtbmF2aWdhdGlvbi1tZW51JyxcbiAgICAgICAgICAgICdAcmFkaXgtdWkvcmVhY3QtcG9wb3ZlcicsXG4gICAgICAgICAgICAnQHJhZGl4LXVpL3JlYWN0LXByb2dyZXNzJyxcbiAgICAgICAgICAgICdAcmFkaXgtdWkvcmVhY3QtcmFkaW8tZ3JvdXAnLFxuICAgICAgICAgICAgJ0ByYWRpeC11aS9yZWFjdC1zY3JvbGwtYXJlYScsXG4gICAgICAgICAgICAnQHJhZGl4LXVpL3JlYWN0LXNlbGVjdCcsXG4gICAgICAgICAgICAnQHJhZGl4LXVpL3JlYWN0LXNlcGFyYXRvcicsXG4gICAgICAgICAgICAnQHJhZGl4LXVpL3JlYWN0LXNsaWRlcicsXG4gICAgICAgICAgICAnQHJhZGl4LXVpL3JlYWN0LXNsb3QnLFxuICAgICAgICAgICAgJ0ByYWRpeC11aS9yZWFjdC1zd2l0Y2gnLFxuICAgICAgICAgICAgJ0ByYWRpeC11aS9yZWFjdC10YWJzJyxcbiAgICAgICAgICAgICdAcmFkaXgtdWkvcmVhY3QtdG9hc3QnLFxuICAgICAgICAgICAgJ0ByYWRpeC11aS9yZWFjdC10b2dnbGUnLFxuICAgICAgICAgICAgJ0ByYWRpeC11aS9yZWFjdC10b2dnbGUtZ3JvdXAnLFxuICAgICAgICAgICAgJ0ByYWRpeC11aS9yZWFjdC10b29sdGlwJyxcbiAgICAgICAgICBdLFxuICAgICAgICAgICdmb3JtLXZlbmRvcic6IFsncmVhY3QtaG9vay1mb3JtJywgJ0Bob29rZm9ybS9yZXNvbHZlcnMnLCAnem9kJ10sXG4gICAgICAgICAgJ3V0aWxzLXZlbmRvcic6IFtcbiAgICAgICAgICAgICdheGlvcycsXG4gICAgICAgICAgICAnY2xzeCcsXG4gICAgICAgICAgICAndGFpbHdpbmQtbWVyZ2UnLFxuICAgICAgICAgICAgJ2NsYXNzLXZhcmlhbmNlLWF1dGhvcml0eScsXG4gICAgICAgICAgICAnZGF0ZS1mbnMnLFxuICAgICAgICAgICAgJ2x1Y2lkZS1yZWFjdCcsXG4gICAgICAgICAgXSxcbiAgICAgICAgICAncXVlcnktdmVuZG9yJzogWydAdGFuc3RhY2svcmVhY3QtcXVlcnknXSxcbiAgICAgICAgfSxcbiAgICAgIH0sXG4gICAgfSxcbiAgICBjaHVua1NpemVXYXJuaW5nTGltaXQ6IDEwMDAsXG4gIH0sXG59KSk7XG4iXSwKICAibWFwcGluZ3MiOiAiO0FBQXVQLFNBQVMsb0JBQW9CO0FBQ3BSLE9BQU8sV0FBVztBQUNsQixPQUFPLFVBQVU7QUFDakIsU0FBUyx5QkFBeUI7QUFDbEMsU0FBUyxhQUFhO0FBSnRCLElBQU0sbUNBQW1DO0FBTXpDLFFBQVEsSUFBSSxtQkFBbUIsUUFBUSxJQUFJLGtCQUFrQjtBQUM3RCxRQUFRLElBQUkseUJBQXlCLFFBQVEsSUFBSSx3QkFBd0I7QUFDekUsUUFBUSxJQUFJLHNCQUFzQixRQUFRLElBQUkscUJBQXFCO0FBR25FLElBQU8sc0JBQVEsYUFBYSxDQUFDLEVBQUUsS0FBSyxPQUFPO0FBQUEsRUFDekMsU0FBUztBQUFBLElBQ1Asa0JBQWtCO0FBQUEsTUFDaEIsUUFBUTtBQUFBO0FBQUEsSUFDVixDQUFDO0FBQUEsSUFDRCxNQUFNO0FBQUEsSUFDTixNQUFNO0FBQUEsRUFDUjtBQUFBLEVBQ0EsU0FBUztBQUFBLElBQ1AsT0FBTztBQUFBLE1BQ0wsS0FBSyxLQUFLLFFBQVEsa0NBQVcsT0FBTztBQUFBLElBQ3RDO0FBQUEsRUFDRjtBQUFBLEVBQ0EsUUFBUTtBQUFBLElBQ04sTUFBTTtBQUFBO0FBQUEsSUFDTixNQUFNLFNBQVMsUUFBUSxJQUFJLGFBQWEsTUFBTTtBQUFBLElBQzlDLE9BQU87QUFBQSxNQUNMLFFBQVE7QUFBQSxRQUNOLFFBQVE7QUFBQSxRQUNSLGNBQWM7QUFBQSxRQUNkLFNBQVM7QUFBQSxRQUNULGNBQWM7QUFBQSxNQUNoQjtBQUFBLElBQ0Y7QUFBQSxJQUNBLE9BQU8sRUFBRSxZQUFZLE1BQU0sVUFBVSxJQUFJO0FBQUEsRUFDM0M7QUFBQSxFQUNBLE9BQU87QUFBQSxJQUNMLGVBQWU7QUFBQSxNQUNiLFFBQVE7QUFBQSxRQUNOLGNBQWM7QUFBQTtBQUFBLFVBRVosZ0JBQWdCLENBQUMsU0FBUyxXQUFXO0FBQUEsVUFDckMsaUJBQWlCLENBQUMsa0JBQWtCO0FBQUEsVUFDcEMsYUFBYTtBQUFBLFlBQ1g7QUFBQSxZQUNBO0FBQUEsWUFDQTtBQUFBLFlBQ0E7QUFBQSxZQUNBO0FBQUEsWUFDQTtBQUFBLFlBQ0E7QUFBQSxZQUNBO0FBQUEsWUFDQTtBQUFBLFlBQ0E7QUFBQSxZQUNBO0FBQUEsWUFDQTtBQUFBLFlBQ0E7QUFBQSxZQUNBO0FBQUEsWUFDQTtBQUFBLFlBQ0E7QUFBQSxZQUNBO0FBQUEsWUFDQTtBQUFBLFlBQ0E7QUFBQSxZQUNBO0FBQUEsWUFDQTtBQUFBLFlBQ0E7QUFBQSxZQUNBO0FBQUEsWUFDQTtBQUFBLFlBQ0E7QUFBQSxZQUNBO0FBQUEsWUFDQTtBQUFBLFVBQ0Y7QUFBQSxVQUNBLGVBQWUsQ0FBQyxtQkFBbUIsdUJBQXVCLEtBQUs7QUFBQSxVQUMvRCxnQkFBZ0I7QUFBQSxZQUNkO0FBQUEsWUFDQTtBQUFBLFlBQ0E7QUFBQSxZQUNBO0FBQUEsWUFDQTtBQUFBLFlBQ0E7QUFBQSxVQUNGO0FBQUEsVUFDQSxnQkFBZ0IsQ0FBQyx1QkFBdUI7QUFBQSxRQUMxQztBQUFBLE1BQ0Y7QUFBQSxJQUNGO0FBQUEsSUFDQSx1QkFBdUI7QUFBQSxFQUN6QjtBQUNGLEVBQUU7IiwKICAibmFtZXMiOiBbXQp9Cg==
