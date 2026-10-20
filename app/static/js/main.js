/**
 * OpsLens Client-Side Helper
 * Handles flash auto-dismissal, duplicate submit protection,
 * demo credentials autofill, and accessible mobile drawer navigation.
 */

document.addEventListener('DOMContentLoaded', () => {
    // 1. Auto-dismiss flash alerts after 6 seconds
    const alerts = document.querySelectorAll('.flash-container .alert, .alert');
    alerts.forEach((alert) => {
        setTimeout(() => {
            alert.style.transition = 'opacity 0.4s ease, transform 0.4s ease';
            alert.style.opacity = '0';
            alert.style.transform = 'translateY(-10px)';
            setTimeout(() => {
                if (alert.parentElement) {
                    alert.remove();
                }
            }, 400);
        }, 6000);
    });

    // 2. Prevent accidental duplicate form submissions
    const forms = document.querySelectorAll('form:not(.no-disable-on-submit)');
    forms.forEach((form) => {
        form.addEventListener('submit', () => {
            const submitBtn = form.querySelector('button[type="submit"]');
            if (submitBtn) {
                submitBtn.dataset.originalText = submitBtn.innerHTML;
                submitBtn.disabled = true;
                submitBtn.innerHTML = 'Processing...';
                // Re-enable after 8 seconds in case response is fast or navigation canceled
                setTimeout(() => {
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = submitBtn.dataset.originalText || 'Submit';
                }, 8000);
            }
        });
    });

    // 3. Accessible Mobile Navigation Drawer
    initMobileNavigation();
});

/**
 * Mobile Navigation Drawer Controller
 * Handles open/close state, backdrop clicks, Escape key, link clicks,
 * body scroll lock, and keyboard focus management for accessibility.
 */
function initMobileNavigation() {
    const toggleBtn = document.getElementById('mobileMenuToggle');
    const drawer = document.getElementById('mobileDrawer');
    const closeBtn = document.getElementById('mobileDrawerClose');
    const backdrop = document.getElementById('drawerBackdrop');

    if (!toggleBtn || !drawer) {
        return;
    }

    function isDrawerOpen() {
        return drawer.classList.contains('nav-drawer-open');
    }

    function openDrawer() {
        drawer.classList.add('nav-drawer-open');
        drawer.setAttribute('aria-hidden', 'false');
        toggleBtn.setAttribute('aria-expanded', 'true');

        if (backdrop) {
            backdrop.classList.add('nav-drawer-open');
            backdrop.setAttribute('aria-hidden', 'false');
        }

        document.body.classList.add('nav-drawer-active');

        // Manage focus: move focus to close button if present, or drawer
        if (closeBtn) {
            closeBtn.focus();
        } else {
            drawer.focus();
        }
    }

    function closeDrawer(restoreFocus) {
        if (restoreFocus === undefined) {
            restoreFocus = true;
        }
        drawer.classList.remove('nav-drawer-open');
        drawer.setAttribute('aria-hidden', 'true');
        toggleBtn.setAttribute('aria-expanded', 'false');

        if (backdrop) {
            backdrop.classList.remove('nav-drawer-open');
            backdrop.setAttribute('aria-hidden', 'true');
        }

        document.body.classList.remove('nav-drawer-active');

        if (restoreFocus && toggleBtn) {
            toggleBtn.focus();
        }
    }

    // Toggle button click
    toggleBtn.addEventListener('click', () => {
        if (isDrawerOpen()) {
            closeDrawer();
        } else {
            openDrawer();
        }
    });

    // Close button click
    if (closeBtn) {
        closeBtn.addEventListener('click', () => closeDrawer());
    }

    // Backdrop click
    if (backdrop) {
        backdrop.addEventListener('click', () => closeDrawer());
    }

    // Close on navigation link click inside drawer
    const drawerLinks = drawer.querySelectorAll('a, button[type="submit"]');
    drawerLinks.forEach((el) => {
        el.addEventListener('click', () => {
            // Do not restore focus to toggle button when navigating away
            closeDrawer(false);
        });
    });

    // Close on Escape key
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && isDrawerOpen()) {
            closeDrawer();
        }
    });

    // Close drawer automatically if viewport resized to desktop (> 768px)
    window.addEventListener('resize', () => {
        if (window.innerWidth > 768 && isDrawerOpen()) {
            closeDrawer(false);
        }
    });
}

/**
 * Quick-fill login credentials for portfolio demonstration
 */
function fillDemoCredentials(username, password) {
    const userField = document.getElementById('username');
    const passField = document.getElementById('password');
    if (userField && passField) {
        userField.value = username;
        passField.value = password;
        userField.focus();
    }
}
