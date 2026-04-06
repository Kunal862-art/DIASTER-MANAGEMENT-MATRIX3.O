// Simple JS for UI interactions
document.addEventListener('DOMContentLoaded', () => {
    // Flash message auto-hide
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        setTimeout(() => {
            alert.style.transition = 'opacity 1s ease-out';
            alert.style.opacity = '0';
            setTimeout(() => alert.remove(), 1000);
        }, 3000);
    });

    // Add some subtle hover effects for report items
    const reportItems = document.querySelectorAll('.report-item, .card');
    reportItems.forEach(item => {
        item.addEventListener('mouseenter', () => {
            item.style.transform = 'scale(1.02)';
            item.style.transition = 'transform 0.2s ease-in-out';
        });
        item.addEventListener('mouseleave', () => {
            item.style.transform = 'scale(1)';
        });
    });
});
