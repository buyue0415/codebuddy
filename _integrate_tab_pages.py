import os

PAGES_DIR = r'c:\Users\28312\WorkBuddy\2026-05-18-task-15\deliverables\v2\src\pages'

# ── 1. Kline.vue ──
path = os.path.join(PAGES_DIR, 'Kline.vue')
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Add imports (after existing data store import)
content = content.replace(
    "import { fmt, apiCall } from '@/api/client.js'",
    "import { fmt, apiCall } from '@/api/client.js'\n"
    "import { useIndustryStore } from '@/stores/industry.js'\n"
    "import IndustryGroupTabs from '@/components/IndustryGroupTabs.vue'"
)

content = content.replace(
    'const data = useDataStore()',
    'const data = useDataStore()\nconst industryStore = useIndustryStore()'
)

# Replace tab-bar template
old_tabs = '''      <div class="tab-bar" v-if="data.watchlist.length">
        <button v-for="s in data.watchlist" :key="s.code" class="tab-btn" :class="{ active: activeCode === s.code }" @click="switchStock(s.code)">{{ s.name }}</button>
      </div>'''

new_tabs = '''      <div v-if="data.watchlist.length">
        <IndustryGroupTabs :stocks="data.watchlist" :activeCode="activeCode"
          @switch="switchStock" />
      </div>'''

content = content.replace(old_tabs, new_tabs)

# Add fetchIndustries to onMounted
content = content.replace(
    "if (!data.watchlist.length) await data.fetchAll()",
    "if (!data.watchlist.length) await data.fetchAll()\n  industryStore.fetchIndustries()"
)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print('Kline.vue: OK')


# ── 2. Intelligence.vue ──
path = os.path.join(PAGES_DIR, 'Intelligence.vue')
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace(
    "import { useDataStore } from '@/stores/data.js'",
    "import { useDataStore } from '@/stores/data.js'\n"
    "import { useIndustryStore } from '@/stores/industry.js'\n"
    "import IndustryGroupTabs from '@/components/IndustryGroupTabs.vue'"
)

content = content.replace(
    'const data = useDataStore()',
    'const data = useDataStore()\nconst industryStore = useIndustryStore()'
)

old_tabs = '''      <div class="tab-bar">
          <button v-for="s in data.watchlist" :key="s.code" class="tab-btn" :class="{ active: activeCode === s.code }" @click="switchStock(s.code)">{{ s.name }}</button>
        </div>'''

new_tabs = '''      <div class="tab-bar">
          <IndustryGroupTabs :stocks="data.watchlist" :activeCode="activeCode"
            @switch="switchStock" />
        </div>'''

content = content.replace(old_tabs, new_tabs)

content = content.replace(
    "if (!data.watchlist.length) await data.fetchAll()",
    "if (!data.watchlist.length) await data.fetchAll()\n  industryStore.fetchIndustries()"
)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print('Intelligence.vue: OK')


# ── 3. Expert.vue ──
path = os.path.join(PAGES_DIR, 'Expert.vue')
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace(
    "import { useDataStore } from '@/stores/data.js'",
    "import { useDataStore } from '@/stores/data.js'\n"
    "import { useIndustryStore } from '@/stores/industry.js'\n"
    "import IndustryGroupTabs from '@/components/IndustryGroupTabs.vue'"
)

content = content.replace(
    'const data = useDataStore()',
    'const data = useDataStore()\nconst industryStore = useIndustryStore()'
)

old_tabs = '''      <div class="tab-bar">
          <button v-for="s in data.watchlist" :key="s.code" class="tab-btn" :class="{ active: activeCode === s.code }" @click="switchStock(s.code)">{{ s.name }}</button>
        </div>'''

new_tabs = '''      <div class="tab-bar">
          <IndustryGroupTabs :stocks="data.watchlist" :activeCode="activeCode"
            @switch="switchStock" />
        </div>'''

content = content.replace(old_tabs, new_tabs)

content = content.replace(
    "if (!data.watchlist.length) await data.fetchAll()",
    "if (!data.watchlist.length) await data.fetchAll()\n  industryStore.fetchIndustries()"
)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print('Expert.vue: OK')


# ── 4. News.vue (special - has "全部" and "重大事件" buttons) ──
path = os.path.join(PAGES_DIR, 'News.vue')
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace(
    "import { useDataStore } from '@/stores/data.js'",
    "import { useDataStore } from '@/stores/data.js'\n"
    "import { useIndustryStore } from '@/stores/industry.js'\n"
    "import IndustryGroupTabs from '@/components/IndustryGroupTabs.vue'"
)

content = content.replace(
    'const data = useDataStore()',
    'const data = useDataStore()\nconst industryStore = useIndustryStore()'
)

# News has "全部" and "重大事件" buttons around the stock buttons
old_news_tabs = '''          <button v-for="s in data.watchlist" :key="s.code" class="tab-btn" :class="{ active: filter === s.code }" @click="setFilter(s.code)">{{ s.name }}</button>'''

new_news_tabs = '''          <IndustryGroupTabs :stocks="data.watchlist" activeCode="" :showToggle="true"
            @switch="(code) => setFilter(code)" />'''

content = content.replace(old_news_tabs, new_news_tabs)

content = content.replace(
    "if (!data.watchlist.length) await data.fetchAll()",
    "if (!data.watchlist.length) await data.fetchAll()\n  industryStore.fetchIndustries()"
)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print('News.vue: OK')


# ── 5. CompanyGraph.vue ──
path = os.path.join(PAGES_DIR, 'CompanyGraph.vue')
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace(
    "import { useCompanyGraphStore } from '@/stores/companyGraph.js'",
    "import { useCompanyGraphStore } from '@/stores/companyGraph.js'\n"
    "import { useIndustryStore } from '@/stores/industry.js'\n"
    "import IndustryGroupTabs from '@/components/IndustryGroupTabs.vue'"
)

old_cg_tabs = '''      <button
          v-for="s in data.watchlist" :key="s.code"
          class="cg-tab" :class="{ active: activeCode === s.code }"
          @click="switchCode(s.code)">{{ s.name }}</button>'''

new_cg_tabs = '''      <IndustryGroupTabs :stocks="data.watchlist" :activeCode="activeCode"
          @switch="switchCode" />'''

content = content.replace(old_cg_tabs, new_cg_tabs)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print('CompanyGraph.vue: OK')

print('\nAll 5 tab pages updated successfully!')
