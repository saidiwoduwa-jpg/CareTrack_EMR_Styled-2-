document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('[data-confirm="true"]').forEach(button => {
    button.closest('form').addEventListener('submit', event => {
      if (!window.confirm(`Are you sure you want to ${button.textContent.trim().toLowerCase()} this account?`)) event.preventDefault();
    });
  });
  document.querySelectorAll('.flash').forEach(item => {
    item.title = 'Click to dismiss';
    item.addEventListener('click', () => item.remove());
  });
});
