// The background job is tied to the figures currently displayed on the page.
(async function () {
    const status = document.getElementById('commentary-status');
    if (!status || !status.dataset.url) return;
    const deadline = Date.now() + 280000;
    while (Date.now() < deadline) {
        await new Promise(resolve => setTimeout(resolve, 2000));
        try {
            const response = await fetch(status.dataset.url, {cache: 'no-store'});
            if (response.status === 401 || response.status === 403) break;
            if (!response.ok) continue;
            const result = await response.json();
            if (result.state === 'pending') continue;
            for (const element of document.querySelectorAll('[data-review-copy]')) {
                const text = result.texts[element.dataset.reviewCopy];
                if (text) element.textContent = text;
            }
            const edition = document.getElementById('review-export-edition');
            if (edition && result.edition) edition.value = result.edition;
            status.textContent = result.state === 'ready'
                ? 'Пояснения подготовлены через Polza по данным этого отчёта.'
                : 'Polza не обновила пояснения. Показаны выводы по текущим цифрам. Можно повторить обновление.';
            return;
        } catch {
            // A transient network failure need not discard the current report.
        }
    }
    status.textContent = 'Не удалось получить статус Polza. Обновите страницу, чтобы проверить результат.';
})();
