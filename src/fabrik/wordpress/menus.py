"""
WordPress Menu Creator - Create and configure navigation menus.

Handles:
- Menu creation
- Menu items (pages, custom links, categories)
- Menu location assignment
"""

import json
from dataclasses import dataclass

from fabrik.drivers.wordpress import WordPressClient, get_wordpress_client


@dataclass
class MenuItem:
    """Menu item details."""

    id: int
    title: str
    url: str
    menu_order: int
    parent_id: int = 0


@dataclass
class CreatedMenu:
    """Created menu details."""

    id: int
    name: str
    slug: str
    items: list[MenuItem]


class MenuCreator:
    """
    Create WordPress navigation menus from site specification.

    Usage:
        creator = MenuCreator("wp-test")
        menu = creator.create_menu("Main Menu", menu_items, location="primary")
    """

    def __init__(self, site_name: str, wp_client: WordPressClient | None = None):
        """
        Initialize menu creator.

        Args:
            site_name: WordPress site name
            wp_client: Optional WP-CLI client
        """
        self.site_name = site_name
        self.wp = wp_client or get_wordpress_client(site_name)
        self._page_cache: dict = {}

    def create_menu(
        self,
        name: str,
        items: list,
        location: str | None = None,
    ) -> CreatedMenu:
        """
        Create a menu with items.

        Args:
            name: Menu name
            items: List of menu items from spec
            location: Theme location (primary, footer, etc.)

        Returns:
            CreatedMenu with details
        """
        # Check if menu exists
        existing_id = self._get_menu_id(name)

        if existing_id:
            # Delete existing menu items
            self.wp.run(
                f"menu item list {existing_id} --format=ids | xargs -r wp menu item delete --allow-root || true"
            )
            menu_id = existing_id
        else:
            # Create new menu
            output = self.wp.run(f"menu create '{name}' --porcelain")
            menu_id = int(output.strip())

        # Add items
        created_items = self._add_items(menu_id, items)

        # Assign to location if specified
        if location:
            self.assign_location(menu_id, location)

        return CreatedMenu(
            id=menu_id,
            name=name,
            slug=name.lower().replace(" ", "-"),
            items=created_items,
        )

    def _add_items(
        self,
        menu_id: int,
        items: list,
        parent_id: int = 0,
        order_start: int = 1,
    ) -> list[MenuItem]:
        """
        Add items to a menu recursively.

        Args:
            menu_id: Menu ID
            items: List of item specs
            parent_id: Parent item ID (0 for top level)
            order_start: Starting menu order

        Returns:
            List of created MenuItem objects
        """
        created = []
        order = order_start

        for item in items:
            # Handle different item formats
            if isinstance(item, str):
                # Simple string - treat as page slug
                item_spec = {"page": item}
            else:
                item_spec = item

            title = item_spec.get("title", "")
            page_slug = item_spec.get("page", "")
            url = item_spec.get("url", "")
            children = item_spec.get("children", [])

            # Determine item type and create
            if page_slug:
                # Link to a page
                page_id = self._get_page_id(page_slug)
                if page_id:
                    output = self.wp.run(
                        f"menu item add-post {menu_id} {page_id} "
                        f"--parent-id={parent_id} --position={order} --porcelain"
                    )
                    item_id = int(output.strip())

                    # Update title if different
                    if title:
                        self.wp.run(f"menu item update {item_id} --title='{title}'")
                else:
                    # Page not found, create as custom link
                    if not title:
                        title = page_slug.replace("-", " ").title()
                    url = f"/{page_slug}/" if page_slug else "/"
                    output = self.wp.run(
                        f"menu item add-custom {menu_id} '{title}' '{url}' "
                        f"--parent-id={parent_id} --position={order} --porcelain"
                    )
                    item_id = int(output.strip())
            elif url:
                # Custom URL
                if not title:
                    title = "Link"
                output = self.wp.run(
                    f"menu item add-custom {menu_id} '{title}' '{url}' "
                    f"--parent-id={parent_id} --position={order} --porcelain"
                )
                item_id = int(output.strip())
            else:
                continue

            created.append(
                MenuItem(
                    id=item_id,
                    title=title or page_slug,
                    url=url or f"/{page_slug}/",
                    menu_order=order,
                    parent_id=parent_id,
                )
            )

            # Handle children
            if children:
                child_items = self._add_items(menu_id, children, parent_id=item_id)
                created.extend(child_items)

            order += 1

        return created

    def _get_page_id(self, slug: str) -> int | None:
        """Get page ID by slug, with caching."""
        if slug in self._page_cache:
            return self._page_cache[slug]

        try:
            # Handle homepage (empty slug)
            if slug == "" or slug == "home":
                output = self.wp.run("option get page_on_front")
                page_id = int(output.strip())
                if page_id > 0:
                    self._page_cache[slug] = page_id
                    return page_id

            output = self.wp.run(f"post list --post_type=page --name='{slug}' --format=ids")
            if output.strip():
                page_id = int(output.strip().split()[0])
                self._page_cache[slug] = page_id
                return page_id
        except (RuntimeError, ValueError):
            pass

        return None

    def _get_menu_id(self, name: str) -> int | None:
        """Get menu ID by name."""
        try:
            output = self.wp.run("menu list --format=json")
            menus = json.loads(output)
            for menu in menus:
                if menu.get("name") == name:
                    return int(menu.get("term_id", 0))
        except (RuntimeError, json.JSONDecodeError):
            pass
        return None

    def assign_location(self, menu_id: int, location: str) -> bool:
        """
        Assign menu to theme location.

        Args:
            menu_id: Menu ID or name
            location: Theme location slug

        Returns:
            True if successful
        """
        try:
            self.wp.run(f"menu location assign {menu_id} {location}")
            return True
        except RuntimeError:
            return False

    def list_menus(self) -> list[dict]:
        """List all menus."""
        try:
            output = self.wp.run("menu list --format=json")
            return json.loads(output)
        except (RuntimeError, json.JSONDecodeError):
            return []

    def list_locations(self) -> list[dict]:
        """List available menu locations."""
        try:
            output = self.wp.run("menu location list --format=json")
            return json.loads(output)
        except (RuntimeError, json.JSONDecodeError):
            return []

    def delete_menu(self, menu_id: int) -> bool:
        """Delete a menu."""
        try:
            self.wp.run(f"menu delete {menu_id}")
            return True
        except RuntimeError:
            return False

    def create_all(self, navigation: dict) -> dict[str, CreatedMenu]:
        """
        Create all menus from navigation spec.

        Args:
            navigation: Navigation section from site spec

        Returns:
            Dict mapping menu name to CreatedMenu
        """
        created = {}

        # Primary menu
        if primary := navigation.get("primary"):
            menu = self.create_menu("Primary Menu", primary, location="primary")
            created["primary"] = menu

        # Footer menu
        if footer := navigation.get("footer"):
            menu = self.create_menu("Footer Menu", footer, location="footer")
            created["footer"] = menu

        # Any other menus
        for key, items in navigation.items():
            if key not in ("primary", "footer") and items:
                menu = self.create_menu(key.title(), items)
                created[key] = menu

        return created


def create_menus(site_name: str, navigation: dict) -> dict[str, CreatedMenu]:
    """
    Convenience function to create menus from navigation spec.

    Args:
        site_name: WordPress site name
        navigation: Navigation section from site spec

    Returns:
        Dict mapping menu name to CreatedMenu
    """
    creator = MenuCreator(site_name)
    return creator.create_all(navigation)
