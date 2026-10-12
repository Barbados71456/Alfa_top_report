const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function setup() {
    const elements = new Map();
    const urls = [];
    const context = vm.createContext({
        URLSearchParams, Intl,
        document: {
            addEventListener() {},
            createElement() {
                return {textContent: '', get innerHTML() {
                    return this.textContent.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
                }};
            },
            getElementById(id) {
                if (!elements.has(id)) elements.set(id, {style: {}, textContent: '', innerHTML: ''});
                return elements.get(id);
            },
        },
        bootstrap: {Modal: class {show() {}}},
        fetch(url) {
            urls.push(new URL(url, 'https://test.invalid'));
            return Promise.resolve({json: async () => ({})});
        },
    });
    vm.runInContext(fs.readFileSync(path.join(__dirname, '../static/detail.js'), 'utf8'), context);
    context.renderCellDetail = () => {};
    context.renderDeviationDetail = () => {};
    return {context, elements, urls};
}

test('cell drill-down sends cumulative mode, allocation and project', async () => {
    const {context, urls, elements} = setup();
    context.showCellDetail({label:'Revenue', lines:['line'], year:2026, month:9,
        pf:'факт', mode:'ytd', allocation:'no_alloc', projects:['Project']});
    assert.equal(urls[0].searchParams.get('mode'), 'ytd');
    assert.equal(urls[0].searchParams.get('allocation'), 'no_alloc');
    assert.equal(urls[0].searchParams.get('project'), 'Project');
    assert.match(elements.get('detailModalTitle').textContent, /накопительно/);
});

test('deviation drill-down preserves cumulative mode and allocation', async () => {
    const {context, urls} = setup();
    context.showDeviationDetail({label:'Revenue', lines:['line'], a:'факт:2026:9',
        b:'факт:2025:9', mode:'ytd', allocation:'no_alloc'});
    assert.equal(urls[0].searchParams.get('mode'), 'ytd');
    assert.equal(urls[0].searchParams.get('allocation'), 'no_alloc');
});

test('source strings are escaped in tooltip and deviation HTML', () => {
    const {context, elements} = setup();
    const hostile = '<img src=x onerror=alert(1)>';
    assert.ok(!context.buildTooltipHtml([{stat3:hostile,val:1}]).includes('<img'));
    context.renderPeriodDeviationDetail({label_a:'A',label_b:'B',total_delta:1,
        drivers:[{project:hostile,stat3:hostile,contragent:hostile,a:1,b:2,delta:1}]});
    const html = elements.get('detailModalBody').innerHTML;
    assert.ok(!html.includes('<img'));
    assert.ok(html.includes('&lt;img'));
});
