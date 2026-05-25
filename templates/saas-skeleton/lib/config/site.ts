export const siteConfig = {
  name: process.env.NEXT_PUBLIC_APP_NAME || "SaaS App",
  description: "Your SaaS application description",
  url: process.env.NEXT_PUBLIC_APP_URL || "",  // Empty = relative URLs
  links: {
    github: "https://github.com/yourusername/yourrepo",
  },
};

export const navConfig = {
  mainNav: [
    { title: "Features", href: "/#features" },
    { title: "Pricing", href: "/pricing" },
    { title: "FAQ", href: "/faq" },
  ],
  appNav: [
    { title: "Dashboard", href: "/app", icon: "LayoutDashboard" },
    { title: "New", href: "/app/new", icon: "Plus" },
    { title: "Items", href: "/app/items", icon: "List" },
    { title: "Settings", href: "/app/settings", icon: "Settings" },
  ],
};
