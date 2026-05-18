<template>
  <Dialog
    class="dialog-stable-height"
    :visible="visible"
    @update:visible="$emit('update:visible', $event)"
    :header="`❓ ${$t('help.title')}`"
    :modal="true"
    :style="{ width: '800px', maxHeight: '90vh' }"
    :closable="true"
  >
    <div class="ajuda-container">
      <TabView class="app-tabview app-tabview--dialog">
        <!-- TAB 1: INTRODUCCIÓ -->
        <TabPanel :header="`📚 ${$t('help.tabs.intro')}`">
          <div class="tab-content">
            <h3>{{ $t('help.intro.welcomeTitle') }}</h3>
            <p>
              {{ $t('help.intro.welcomeBody') }}
            </p>

            <h4>{{ $t('help.intro.featuresTitle') }}</h4>
            <ul>
              <li>📋 {{ $t('help.intro.features.items.substitutions') }}</li>
              <li>👁️ {{ $t('help.intro.features.items.vigilancies') }}</li>
              <li>🎓 {{ $t('help.intro.features.items.groups') }}</li>
              <li>📄 {{ $t('help.intro.features.items.pdf') }}</li>
              <li>📊 {{ $t('help.intro.features.items.stats') }}</li>
            </ul>

            <h4>{{ $t('help.intro.navigationTitle') }}</h4>
            <p>{{ $t('help.intro.navigationBody') }}</p>
            <ul>
              <li><strong>{{ $t('help.intro.navigation.items.substitutionsTitle') }}:</strong> {{ $t('help.intro.navigation.items.substitutionsBody') }}</li>
              <li><strong>{{ $t('help.intro.navigation.items.groupsTitle') }}:</strong> {{ $t('help.intro.navigation.items.groupsBody') }}</li>
              <li><strong>{{ $t('help.intro.navigation.items.vigilanciesTitle') }}:</strong> {{ $t('help.intro.navigation.items.vigilanciesBody') }}</li>
            </ul>
          </div>
        </TabPanel>

        <!-- TAB 2: SUBSTITUCIONS -->
        <TabPanel :header="`📋 ${$t('help.tabs.substitutions')}`">
          <div class="tab-content">
            <h3>{{ $t('help.substitutions.title') }}</h3>

            <div class="help-section">
              <h4>⚡ {{ $t('help.substitutions.generatePending.title') }}</h4>
              <p>
                {{ $t('help.substitutions.generatePending.body') }}
              </p>
            </div>

            <div class="help-section">
              <h4>🔄 {{ $t('help.substitutions.regenerate.title') }}</h4>
              <p>
                <span v-html="$t('help.substitutions.regenerate.body')"></span>
              </p>
            </div>

            <div class="help-section">
              <h4>➕ {{ $t('help.substitutions.newAbsence.title') }}</h4>
              <p>
                {{ $t('help.substitutions.newAbsence.body') }}
              </p>
            </div>

            <div class="help-section">
              <h4>📄 {{ $t('help.substitutions.savePdf.title') }}</h4>
              <p>
                {{ $t('help.substitutions.savePdf.body') }}
              </p>
            </div>

            <div class="help-section">
              <h4>{{ $t('help.substitutions.assignManual.title') }}</h4>
              <p>
                {{ $t('help.substitutions.assignManual.body') }}
              </p>
              <ul>
                <li><strong style="color: #2ecc71;">{{ $t('help.substitutions.assignManual.colors.free.title') }}:</strong> {{ $t('help.substitutions.assignManual.colors.free.body') }}</li>
                <li><strong style="color: #3498db;">{{ $t('help.substitutions.assignManual.colors.guard.title') }}:</strong> {{ $t('help.substitutions.assignManual.colors.guard.body') }}</li>
                <li><strong style="color: #f39c12;">{{ $t('help.substitutions.assignManual.colors.available.title') }}:</strong> {{ $t('help.substitutions.assignManual.colors.available.body') }}</li>
                <li><strong style="color: #e74c3c;">{{ $t('help.substitutions.assignManual.colors.assigned.title') }}:</strong> {{ $t('help.substitutions.assignManual.colors.assigned.body') }}</li>
              </ul>
            </div>
          </div>
        </TabPanel>

        <!-- TAB 3: VIGILÀNCIES -->
        <TabPanel :header="`👁️ ${$t('help.tabs.vigilancies')}`">
          <div class="tab-content">
            <h3>{{ $t('help.vigilancies.title') }}</h3>

            <div class="help-section">
              <h4>➕ {{ $t('help.vigilancies.new.title') }}</h4>
              <p>
                {{ $t('help.vigilancies.new.body') }}
              </p>
            </div>

            <div class="help-section">
              <h4>🎯 {{ $t('help.vigilancies.assignOwners.title') }}</h4>
              <p>
                <span v-html="$t('help.vigilancies.assignOwners.body')"></span>
              </p>
            </div>

            <div class="help-section">
              <h4>📋 {{ $t('help.vigilancies.assignPending.title') }}</h4>
              <p>
                {{ $t('help.vigilancies.assignPending.body') }}
              </p>
              <ol>
                <li><strong>{{ $t('help.vigilancies.assignPending.steps.free.title') }}:</strong> {{ $t('help.vigilancies.assignPending.steps.free.body') }}</li>
                <li><strong>{{ $t('help.vigilancies.assignPending.steps.available.title') }}:</strong> {{ $t('help.vigilancies.assignPending.steps.available.body') }}</li>
              </ol>
            </div>

            <div class="help-section">
              <h4>📄 {{ $t('help.vigilancies.export.title') }}</h4>
              <p>
                {{ $t('help.vigilancies.export.body') }}
              </p>
              <ul>
                <li>{{ $t('help.vigilancies.export.items.levels') }}</li>
                <li>{{ $t('help.vigilancies.export.items.comments') }}</li>
                <li>{{ $t('help.vigilancies.export.items.compress') }}</li>
              </ul>
            </div>

            <div class="help-section">
              <h4>📅 {{ $t('help.vigilancies.interval.title') }}</h4>
              <p>
                {{ $t('help.vigilancies.interval.body') }}
              </p>
            </div>
          </div>
        </TabPanel>

        <!-- TAB 4: CONFIGURACIÓ -->
        <TabPanel :header="`⚙️ ${$t('help.tabs.config')}`">
          <div class="tab-content">
            <h3>{{ $t('help.config.title') }}</h3>

            <div class="help-section">
              <h4>⚙️ {{ $t('help.config.general.title') }}</h4>
              <p>{{ $t('help.config.general.body') }}</p>
              <ul>
                <li><strong>{{ $t('help.config.general.items.institution.title') }}:</strong> {{ $t('help.config.general.items.institution.body') }}</li>
                <li><strong>{{ $t('help.config.general.items.language.title') }}:</strong> {{ $t('help.config.general.items.language.body') }}</li>
                <li><strong>{{ $t('help.config.general.items.xml.title') }}:</strong> {{ $t('help.config.general.items.xml.body') }}</li>
                <li><strong>{{ $t('help.config.general.items.export.title') }}:</strong> {{ $t('help.config.general.items.export.body') }}</li>
              </ul>
            </div>

            <div class="help-section">
              <h4>⚡ {{ $t('help.config.exam.title') }}</h4>
              <p>{{ $t('help.config.exam.body') }}</p>
              <ul>
                <li><strong>{{ $t('help.config.exam.items.subjects.title') }}:</strong> {{ $t('help.config.exam.items.subjects.body') }}</li>
                <li><strong>{{ $t('help.config.exam.items.groups.title') }}:</strong> {{ $t('help.config.exam.items.groups.body') }}</li>
                <li><strong>{{ $t('help.config.exam.items.rooms.title') }}:</strong> {{ $t('help.config.exam.items.rooms.body') }}</li>
              </ul>
            </div>
          </div>
        </TabPanel>

        <!-- TAB 5: CONSELLS -->
        <TabPanel :header="`💡 ${$t('help.tabs.tips')}`">
          <div class="tab-content">
            <h3>{{ $t('help.tips.title') }}</h3>

            <div class="help-section">
              <h4>1. {{ $t('help.tips.substitutions.title') }}</h4>
              <ol>
                <li>{{ $t('help.tips.substitutions.steps.selectDate') }}</li>
                <li>{{ $t('help.tips.substitutions.steps.addAbsence') }}</li>
                <li>{{ $t('help.tips.substitutions.steps.generate') }}</li>
                <li>{{ $t('help.tips.substitutions.steps.review') }}</li>
                <li>{{ $t('help.tips.substitutions.steps.pdf') }}</li>
              </ol>
            </div>

            <div class="help-section">
              <h4>2. {{ $t('help.tips.vigilancies.title') }}</h4>
              <ul>
                <li>{{ $t('help.tips.vigilancies.items.define') }}</li>
                <li>{{ $t('help.tips.vigilancies.items.assignOwners') }}</li>
                <li>{{ $t('help.tips.vigilancies.items.assignPending') }}</li>
                <li>{{ $t('help.tips.vigilancies.items.adjust') }}</li>
              </ul>
            </div>

            <div class="help-section">
              <h4>3. {{ $t('help.tips.groups.title') }}</h4>
              <p>
                {{ $t('help.tips.groups.body') }}
              </p>
            </div>

            <div class="help-section">
              <h4>4. {{ $t('help.tips.filters.title') }}</h4>
              <p>
                {{ $t('help.tips.filters.body') }}
              </p>
              <ul>
                <li>{{ $t('help.tips.filters.items.level') }}</li>
                <li>{{ $t('help.tips.filters.items.hour') }}</li>
                <li>{{ $t('help.tips.filters.items.status') }}</li>
              </ul>
            </div>
          </div>
        </TabPanel>
      </TabView>
    </div>

    <template #footer>
      <div class="footer-info">
        <span class="version-info">{{ $t('help.footerVersion') }}</span>
        <Button
          :label="$t('common.close')"
          icon="pi pi-times"
          @click="tancar"
          class="p-button-text"
        />
      </div>
    </template>
  </Dialog>
</template>

<script setup>
import Dialog from 'primevue/dialog'
import TabView from 'primevue/tabview'
import TabPanel from 'primevue/tabpanel'
import Button from 'primevue/button'

const props = defineProps({
  visible: {
    type: Boolean,
    required: true
  }
})

const emit = defineEmits(['update:visible'])

const tancar = () => {
  emit('update:visible', false)
}
</script>

<style scoped>
.ajuda-container {
  padding: 0.5rem 0;
}

.tab-content {
  padding: 1.5rem;
  max-height: 500px;
  overflow-y: auto;
}

.tab-content h3 {
  font-size: 1.5rem;
  color: #2c3e50;
  margin-bottom: 1rem;
  padding-bottom: 0.5rem;
  border-bottom: 2px solid #667eea;
}

.tab-content h4 {
  font-size: 1.1rem;
  color: #34495e;
  margin-top: 1.5rem;
  margin-bottom: 0.75rem;
}

.tab-content p {
  color: #5a6c7d;
  line-height: 1.6;
  margin-bottom: 1rem;
}

.tab-content ul,
.tab-content ol {
  color: #5a6c7d;
  line-height: 1.8;
  margin-left: 1.5rem;
  margin-bottom: 1rem;
}

.tab-content li {
  margin-bottom: 0.5rem;
}

.help-section {
  background: #f9fafb;
  padding: 1.25rem;
  border-radius: 8px;
  margin-bottom: 1.5rem;
  border-left: 4px solid #667eea;
}

.help-section h4 {
  margin-top: 0;
  color: #667eea;
}

.help-section:last-child {
  margin-bottom: 0;
}

.footer-info {
  width: 100%;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.version-info {
  color: #6b7280;
  font-size: 0.85rem;
  font-style: italic;
}

/* Scrollbar personalitzat */
.tab-content::-webkit-scrollbar {
  width: 8px;
}

.tab-content::-webkit-scrollbar-track {
  background: #f1f1f1;
  border-radius: 4px;
}

.tab-content::-webkit-scrollbar-thumb {
  background: #cbd5e0;
  border-radius: 4px;
}

.tab-content::-webkit-scrollbar-thumb:hover {
  background: #a0aec0;
}
</style>
