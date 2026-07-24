<template>
  <Dialog
    class="dialog-stable-height"
    :visible="visible"
    @update:visible="handleVisibleChange"
    :header="$t('config.title')"
    :modal="true"
    :style="{ width: '900px', maxHeight: '90vh' }"
    :closable="true"
  >
    <div class="config-container">
      <TabView class="app-tabview app-tabview--dialog">
        <!-- TAB 1: SISTEMA I FITXERS -->
        <TabPanel>
          <template #header>
            <span class="tab-header-lines">
              <span>{{ $t('config.tabs.systemLine1') }}</span>
              <span>{{ $t('config.tabs.systemLine2') }}</span>
            </span>
          </template>
          <SystemTab :current-role="currentRole" @update:dirty="systemDirty = $event" />
        </TabPanel>

      <!-- TAB 2: GRUPS I ABREVIATURES -->
        <TabPanel>
          <template #header>
            <span class="tab-header-lines">
              <span>{{ $t('config.tabs.groupsLine1') }}</span>
              <span>{{ $t('config.tabs.groupsLine2') }}</span>
            </span>
          </template>
          <GrupsTab :dataGlobal="dataGlobal" />
        </TabPanel>

      <!-- TAB 3: PROFESSORS DE BAIXA -->
        <TabPanel>
          <template #header>
            <span class="tab-header-lines">
              <span>{{ $t('config.tabs.leaveLine1') }}</span>
              <span>{{ $t('config.tabs.leaveLine2') }}</span>
            </span>
          </template>
          <BaixesTab />
        </TabPanel>

        <!-- TAB 4: PRIORITATS -->
        <TabPanel>
          <template #header>
            <span class="tab-header-lines">
              <span>{{ $t('config.tabs.prioritiesLine1') }}</span>
              <span>&nbsp;</span>
            </span>
          </template>
          <PrioritatsTab :dataGlobal="dataGlobal" />
        </TabPanel>

        <!-- TAB 5: CURSOS -->
        <TabPanel v-if="canManageUsers">
          <template #header>
            <span class="tab-header-lines">
              <span>{{ $t('config.tabs.coursesLine1') }}</span>
              <span>&nbsp;</span>
            </span>
          </template>
          <CursosTab @cursos-canviats="emit('cursos-canviats')" />
        </TabPanel>

        <!-- TAB: GOVERNANÇA DE DADES (RGPD) -->
        <TabPanel v-if="canManageUsers">
          <template #header>
            <span class="tab-header-lines">
              <span>{{ $t('config.tabs.dataLine1') }}</span>
              <span>{{ $t('config.tabs.dataLine2') }}</span>
            </span>
          </template>
          <GestioDadesTab />
        </TabPanel>

        <!-- TAB 6: USUARIS -->
        <TabPanel v-if="canManageUsers">
          <template #header>
            <span class="tab-header-lines">
              <span>{{ $t('config.tabs.usersLine1') }}</span>
              <span>&nbsp;</span>
            </span>
          </template>
          <UsuarisTab :current-role="currentRole" :current-institucio="currentInstitucio" />
        </TabPanel>

        <!-- TAB 6: INSTITUCIONS (SUPER ADMIN) -->
        <TabPanel v-if="isSuperAdmin">
          <template #header>
            <span class="tab-header-lines">
              <span>{{ $t('config.tabs.institutionsLine1') }}</span>
              <span>&nbsp;</span>
            </span>
          </template>
          <InstitucionsTab />
        </TabPanel>
      </TabView>
    </div>

    <template #footer>
      <Button
        :label="$t('common.close')"
        icon="pi pi-times"
        @click="tancar"
        class="p-button-text"
      />
    </template>
  </Dialog>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useConfirm } from 'primevue/useconfirm'
import Dialog from 'primevue/dialog'
import Button from 'primevue/button'
import TabView from 'primevue/tabview'
import TabPanel from 'primevue/tabpanel'
import SystemTab from './config/SystemTab.vue'
import GrupsTab from './config/GrupsTab.vue'
import BaixesTab from './config/BaixesTab.vue'
import PrioritatsTab from './config/PrioritatsTab.vue'
import CursosTab from './config/CursosTab.vue'
import GestioDadesTab from './config/GestioDadesTab.vue'
import UsuarisTab from './config/UsuarisTab.vue'
import InstitucionsTab from './config/InstitucionsTab.vue'

const { t } = useI18n()
const confirm = useConfirm()

const props = defineProps({
  visible: {
    type: Boolean,
    required: true
  },
  currentRole: {
    type: String,
    default: null
  },
  currentInstitucio: {
    type: String,
    default: null
  },
  dataGlobal: {
    type: Date,
    default: () => new Date()
  }
})

const emit = defineEmits(['update:visible', 'cursos-canviats'])

const canManageUsers = computed(() => ['admin', 'super_admin'].includes(props.currentRole || ''))
const isSuperAdmin = computed(() => props.currentRole === 'super_admin')

// Estat "hi ha canvis sense desar" del tab Sistema: governa la confirmació
// de tancament del diàleg (com abans, només depèn dels settings del sistema).
const systemDirty = ref(false)

const handleVisibleChange = (newVal) => {
  if (newVal) {
    emit('update:visible', true)
    return
  }

  if (!systemDirty.value) {
    emit('update:visible', false)
    return
  }

  confirm.require({
    message: t('common.unsavedChangesPrompt'),
    header: t('common.unsavedChangesTitle'),
    icon: 'pi pi-exclamation-triangle',
    acceptLabel: t('common.closeAnyway'),
    rejectLabel: t('common.cancel'),
    accept: () => {
      emit('update:visible', false)
    }
  })
}

const tancar = () => {
  handleVisibleChange(false)
}
</script>

<style scoped>
.config-container {
  padding: 0.75rem 0.75rem 0.5rem;
}

:deep(.p-dialog-content) {
  padding: 1rem 1rem 0.75rem !important;
}

.tab-header-lines {
  display: inline-flex;
  flex-direction: column;
  justify-content: center;
  line-height: 1.08;
}

.tab-header-lines span {
  display: block;
  white-space: nowrap;
}
</style>
