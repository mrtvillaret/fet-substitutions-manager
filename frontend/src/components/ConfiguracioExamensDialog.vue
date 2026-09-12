<template>
  <Dialog
    class="dialog-stable-height"
    :visible="visible"
    @update:visible="$emit('update:visible', $event)"
    :header="$t('examConfig.title')"
    :modal="true"
    :style="{ width: '900px', maxHeight: '90vh' }"
    :closable="true"
  >
    <div v-if="loading" class="loading">
      <i class="pi pi-spin pi-spinner" style="font-size: 2rem;"></i>
      <p>{{ $t('common.loadingConfig') }}</p>
    </div>

    <div v-else class="config-container">
      <TabView class="app-tabview app-tabview--dialog">
        <!-- TAB 0: IMPORTACIÓ / EXPORTACIÓ -->
        <TabPanel :header="$t('examConfig.tabs.import')">
          <div class="tab-content">
            <Message severity="info" :closable="false">
              {{ $t('examConfig.import.tabIntro') }}
            </Message>

            <div class="import-section">
              <h4>{{ $t('examConfig.import.mainTitle') }}</h4>
              <p class="import-section-desc">{{ $t('examConfig.import.mainDesc') }}</p>
              <div class="import-buttons-row">
                <Button
                  :label="$t('examConfig.import.button')"
                  icon="pi pi-download"
                  @click="obrirImportacio"
                  class="p-button-help"
                />
                <Button
                  :label="$t('examConfig.import.exportCsv')"
                  icon="pi pi-file-export"
                  @click="exportarAssignacionsCsv"
                  class="p-button-secondary"
                  :disabled="assignacions.length === 0"
                />
                <Button
                  :label="$t('examConfig.import.importCsv')"
                  icon="pi pi-file-import"
                  @click="triarFitxerCsv"
                  class="p-button-secondary"
                />
                <input
                  ref="inputCsvRef"
                  type="file"
                  accept=".csv"
                  style="display: none"
                  @change="onFitxerCsvSeleccionat"
                />
              </div>
            </div>
          </div>
        </TabPanel>

        <!-- TAB 1: NIVELLS -->
        <TabPanel :header="$t('examConfig.tabs.levels')">
          <div class="tab-content">
            <div class="toolbar">
              <div class="toolbar-left">
                <Tag severity="info" :value="$t('examConfig.levels.count', { count: nivells.length })" />
              </div>
              <div class="toolbar-right">
                <Button
                  :label="$t('common.add')"
                  icon="pi pi-plus"
                  @click="mostrarDialogAfegirNivell = true"
                  size="small"
                  class="p-button-success"
                />
              </div>
            </div>

            <div class="items-list">
              <div
                v-for="(nivell, idx) in nivells"
                :key="idx"
                class="item-card"
              >
                <span class="item-name">{{ nivell }}</span>
                <div class="item-actions">
                  <Button
                    icon="pi pi-pencil"
                    @click="prepararRenomNivell(nivell)"
                    class="p-button-rounded p-button-text p-button-warning p-button-sm"
                    v-tooltip.top="$t('common.edit')"
                  />
                  <Button
                    icon="pi pi-trash"
                    @click="eliminarNivell(nivell)"
                    class="p-button-rounded p-button-text p-button-danger p-button-sm"
                    v-tooltip.top="$t('common.delete')"
                  />
                </div>
              </div>
              <div v-if="nivells.length === 0" class="empty-message">
                {{ $t('examConfig.levels.empty') }}
              </div>
            </div>
            <p class="info-text">
              <i class="pi pi-info-circle"></i>
              {{ $t('examConfig.levels.hint') }}
            </p>
          </div>
        </TabPanel>

        <!-- TAB 2: GRUPS -->
        <TabPanel :header="$t('examConfig.tabs.groups')">
          <div class="tab-content">
            <div class="toolbar">
              <Dropdown
                v-model="nivellSeleccionatGrups"
                :options="nivells"
                :placeholder="$t('examConfig.groups.selectLevel')"
                @change="carregarGrups"
                class="nivell-selector"
              />
              <Button
                :label="$t('common.add')"
                icon="pi pi-plus"
                @click="mostrarDialogAfegirGrup = true"
                size="small"
                class="p-button-success"
              />
            </div>

            <div v-if="nivellSeleccionatGrups" class="items-list">
              <div
                v-for="(grup, idx) in grups"
                :key="idx"
                class="item-card"
              >
                <span class="item-name">{{ grup }}</span>
                <div class="item-actions">
                  <Button
                    icon="pi pi-pencil"
                    @click="prepararRenomGrup(grup)"
                    class="p-button-rounded p-button-text p-button-warning p-button-sm"
                    v-tooltip.top="$t('common.edit')"
                  />
                  <Button
                    icon="pi pi-trash"
                    @click="eliminarGrup(grup)"
                    class="p-button-rounded p-button-text p-button-danger p-button-sm"
                    v-tooltip.top="$t('common.delete')"
                  />
                </div>
              </div>
              <div v-if="grups.length === 0" class="empty-message">
                {{ $t('examConfig.groups.empty') }}
              </div>
            </div>
            <div v-else class="select-nivell-message">
              {{ $t('examConfig.groups.selectLevelHint') }}
            </div>
          </div>
        </TabPanel>

        <!-- TAB 3: ASSIGNATURES -->
        <TabPanel :header="$t('examConfig.tabs.subjects')">
          <div class="tab-content">
            <div class="toolbar">
              <Dropdown
                v-model="nivellSeleccionat"
                :options="nivells"
                :placeholder="$t('examConfig.subjects.selectLevel')"
                @change="carregarAssignatures"
                class="nivell-selector"
              />
              <Button
                :label="$t('common.add')"
                icon="pi pi-plus"
                @click="mostrarDialogAfegirAssignatura = true"
                size="small"
                class="p-button-success"
              />
            </div>

            <div v-if="nivellSeleccionat" class="items-list">
              <div
                v-for="(assignatura, idx) in assignatures"
                :key="idx"
                class="item-card"
              >
                <span class="item-name">{{ assignatura }}</span>
                <div class="item-actions">
                  <Button
                    icon="pi pi-pencil"
                    @click="prepararRenomAssignatura(assignatura)"
                    class="p-button-rounded p-button-text p-button-warning p-button-sm"
                    v-tooltip.top="$t('common.edit')"
                  />
                  <Button
                    icon="pi pi-trash"
                    @click="eliminarAssignatura(assignatura)"
                    class="p-button-rounded p-button-text p-button-danger p-button-sm"
                    v-tooltip.top="$t('common.delete')"
                  />
                </div>
              </div>
              <div v-if="assignatures.length === 0" class="empty-message">
                {{ $t('examConfig.subjects.empty') }}
              </div>
            </div>
            <div v-else class="select-nivell-message">
              {{ $t('examConfig.subjects.selectLevelHint') }}
            </div>
          </div>
        </TabPanel>

        <!-- TAB 4: AULES -->
        <TabPanel :header="$t('examConfig.tabs.rooms')">
          <div class="tab-content">
            <div class="toolbar">
              <div class="toolbar-left">
                <Tag severity="info" :value="$t('examConfig.rooms.count', { count: aules.length })" />
              </div>
              <Button
                :label="$t('common.add')"
                icon="pi pi-plus"
                @click="mostrarDialogAfegirAula = true"
                size="small"
                class="p-button-success"
              />
            </div>

            <div class="items-list">
              <div
                v-for="(aula, idx) in aules"
                :key="idx"
                class="item-card"
              >
                <span class="item-name">{{ aula }}</span>
                <div class="item-actions">
                  <Button
                    icon="pi pi-pencil"
                    @click="prepararRenomAula(aula)"
                    class="p-button-rounded p-button-text p-button-warning p-button-sm"
                    v-tooltip.top="$t('common.edit')"
                  />
                  <Button
                    icon="pi pi-trash"
                    @click="eliminarAula(aula)"
                    class="p-button-rounded p-button-text p-button-danger p-button-sm"
                    v-tooltip.top="$t('common.delete')"
                  />
                </div>
              </div>
              <div v-if="aules.length === 0" class="empty-message">
                {{ $t('examConfig.rooms.empty') }}
              </div>
            </div>
          </div>
        </TabPanel>

        <!-- TAB 5: ASSIGNACIONS PROFESSOR-TITULAR -->
        <TabPanel :header="$t('examConfig.tabs.assignments')">
          <div class="tab-content-table">
            <!-- Filtres -->
            <div class="filtres-assignacions">
              <div class="filtre-group">
                <label>{{ $t('examConfig.assignments.filterLevel') }}</label>
                <Dropdown
                  v-model="filtreNivellAssignacions"
                  :options="[$t('common.all'), ...nivells]"
                  :placeholder="$t('common.all')"
                  @change="filtrarAssignacions"
                  class="filtre-dropdown"
                />
              </div>
              <div class="filtre-group">
                <label>{{ $t('examConfig.assignments.filterSubject') }}</label>
                <Dropdown
                  v-model="filtreAssignaturaAssignacions"
                  :options="[$t('common.all'), ...assignaturesUniques]"
                  :placeholder="$t('common.all')"
                  @change="filtrarAssignacions"
                  class="filtre-dropdown"
                />
              </div>
              <div class="toolbar-right">
                <Tag severity="info" :value="$t('examConfig.assignments.count', { shown: assignacionsFiltrades.length, total: assignacions.length })" />
                <Button
                  :label="$t('examConfig.assignments.newRow')"
                  icon="pi pi-plus"
                  @click="afegirFilaAssignacio"
                  size="small"
                  class="p-button-success"
                />
                <Button
                  :label="$t('examConfig.assignments.deleteFiltered')"
                  icon="pi pi-trash"
                  @click="eliminarAssignacionsFiltrades"
                  size="small"
                  class="p-button-danger p-button-outlined"
                  :disabled="assignacionsFiltrades.length === 0"
                />
                <Button
                  :label="$t('examConfig.assignments.deleteAll')"
                  icon="pi pi-trash"
                  @click="eliminarTotesAssignacions"
                  size="small"
                  class="p-button-danger"
                  :disabled="assignacions.length === 0"
                />
              </div>
            </div>

            <!-- Taula inline editable -->
            <DataTable
              :value="assignacionsFiltrades"
              :paginator="true"
              :rows="15"
              :rowsPerPageOptions="[15, 30, 50, 100]"
              editMode="cell"
              @cell-edit-complete="onCellEditComplete"
              stripedRows
              showGridlines
              responsiveLayout="scroll"
              class="assignacions-table p-datatable-sm"
            >
              <Column field="assignatura" :header="$t('common.subject')" sortable style="min-width: 200px">
                <template #editor="{ data, field }">
                  <Dropdown
                    v-model="data[field]"
                    :options="['', ...totesAssignatures]"
                    :placeholder="$t('examConfig.assignments.selectSubject')"
                    class="w-full p-inputtext-sm"
                    :filter="true"
                  />
                </template>
              </Column>
              <Column field="grup" :header="$t('common.group')" sortable style="min-width: 130px">
                <template #editor="{ data, field }">
                  <Dropdown
                    v-model="data[field]"
                    :options="['', ...totsGrups]"
                    :placeholder="$t('examConfig.assignments.selectGroup')"
                    class="w-full p-inputtext-sm"
                  />
                </template>
              </Column>
              <Column field="titular" :header="$t('examConfig.assignments.owner')" sortable style="min-width: 150px">
                <template #body="slotProps">
                  <span>{{ slotProps.data.titular || $t('common.noneDash') }}</span>
                </template>
                <template #editor="{ data, field }">
                  <Dropdown
                    v-model="data[field]"
                    :options="['', ...professors]"
                    :placeholder="$t('examConfig.assignments.selectTeacher')"
                    class="w-full p-inputtext-sm"
                    :filter="true"
                  />
                </template>
              </Column>
              <Column field="aula" :header="$t('common.room')" sortable style="min-width: 150px">
                <template #body="slotProps">
                  <span>{{ slotProps.data.aula || $t('common.noneDash') }}</span>
                </template>
                <template #editor="{ data, field }">
                  <Dropdown
                    v-model="data[field]"
                    :options="['', ...aules]"
                    :placeholder="$t('examConfig.assignments.selectRoom')"
                    class="w-full p-inputtext-sm"
                  />
                </template>
              </Column>
              <Column :header="$t('common.actions')" style="width: 100px" :frozen="true" alignFrozen="right">
                <template #body="slotProps">
                  <Button
                    icon="pi pi-trash"
                    @click="eliminarAssignacio(slotProps.data.id)"
                    class="p-button-rounded p-button-text p-button-danger p-button-sm"
                    v-tooltip.top="$t('common.delete')"
                  />
                </template>
              </Column>
            </DataTable>
          </div>
        </TabPanel>

        <!-- TAB 6: AFINITATS -->
        <TabPanel :header="$t('examConfig.tabs.affinities')">
          <div class="tab-content-table">
            <div class="filtres-assignacions">
              <div class="filtre-group">
                <label>{{ $t('examConfig.affinities.title') }}</label>
                <small class="text-muted">{{ $t('examConfig.affinities.subtitle') }}</small>
              </div>
              <div class="toolbar-right">
                <Button
                  :label="$t('common.add')"
                  icon="pi pi-plus"
                  @click="afegirFilaAfinitat"
                  size="small"
                  class="p-button-success"
                />
                <Button
                  :label="$t('common.save')"
                  icon="pi pi-save"
                  @click="desarAfinitats"
                  size="small"
                  class="p-button-primary"
                />
              </div>
            </div>

            <Message severity="info" :closable="false" class="mb-3">
              {{ $t('examConfig.affinities.flowInfo') }}
            </Message>

            <DataTable
              :value="afinitats"
              stripedRows
              showGridlines
              responsiveLayout="scroll"
              class="assignacions-table p-datatable-sm"
            >
              <Column field="base" :header="$t('examConfig.affinities.base')" style="min-width: 180px">
                <template #body="{ data }">
                  <InputText v-model="data.base" class="w-full p-inputtext-sm" />
                </template>
              </Column>
              <Column field="ordreText" :header="$t('examConfig.affinities.order')" style="min-width: 420px">
                <template #body="{ data }">
                  <InputText v-model="data.ordreText" class="w-full p-inputtext-sm" :placeholder="$t('examConfig.affinities.orderPlaceholder')" />
                </template>
              </Column>
              <Column :header="$t('common.actions')" style="width: 90px" :frozen="true" alignFrozen="right">
                <template #body="{ index }">
                  <Button
                    icon="pi pi-trash"
                    class="p-button-rounded p-button-text p-button-danger p-button-sm"
                    @click="eliminarFilaAfinitat(index)"
                    v-tooltip.top="$t('common.delete')"
                  />
                </template>
              </Column>
            </DataTable>
          </div>
        </TabPanel>

      </TabView>
    </div>

    <!-- Diàleg afegir nivell -->
    <Dialog
      v-model:visible="mostrarDialogAfegirNivell"
      :header="$t('examConfig.levels.addTitle')"
      :modal="true"
      :style="{ width: '400px' }"
    >
      <div class="p-fluid">
        <div class="field">
          <label>{{ $t('examConfig.levels.codeLabel') }}</label>
          <InputText
            v-model="nouNivell"
            :placeholder="$t('examConfig.levels.codePlaceholder')"
            @keyup.enter="afegirNivell"
          />
        </div>
      </div>

      <template #footer>
        <Button :label="$t('common.cancel')" @click="mostrarDialogAfegirNivell = false" class="p-button-text" />
        <Button
          :label="$t('common.add')"
          @click="afegirNivell"
          class="p-button-success"
          :disabled="!nouNivell"
        />
      </template>
    </Dialog>

    <!-- Diàleg afegir assignatura -->
    <Dialog
      v-model:visible="mostrarDialogAfegirAssignatura"
      :header="$t('examConfig.subjects.addTitle')"
      :modal="true"
      :style="{ width: '400px' }"
    >
      <div class="p-fluid">
        <div class="field">
          <label>{{ $t('examConfig.subjects.nameLabel') }}</label>
          <InputText
            v-model="novaAssignatura"
            :placeholder="$t('examConfig.subjects.namePlaceholder')"
            @keyup.enter="afegirAssignatura"
          />
        </div>
      </div>

      <template #footer>
        <Button :label="$t('common.cancel')" @click="mostrarDialogAfegirAssignatura = false" class="p-button-text" />
        <Button
          :label="$t('common.add')"
          @click="afegirAssignatura"
          class="p-button-success"
          :disabled="!novaAssignatura"
        />
      </template>
    </Dialog>

    <!-- Diàleg afegir grup -->
    <Dialog
      v-model:visible="mostrarDialogAfegirGrup"
      :header="$t('examConfig.groups.addTitle')"
      :modal="true"
      :style="{ width: '400px' }"
    >
      <div class="p-fluid">
        <div class="field">
          <label>{{ $t('examConfig.groups.codeLabel') }}</label>
          <InputText
            v-model="nouGrup"
            :placeholder="$t('examConfig.groups.codePlaceholder')"
            @keyup.enter="afegirGrup"
          />
        </div>
      </div>

      <template #footer>
        <Button :label="$t('common.cancel')" @click="mostrarDialogAfegirGrup = false" class="p-button-text" />
        <Button
          :label="$t('common.add')"
          @click="afegirGrup"
          class="p-button-success"
          :disabled="!nouGrup"
        />
      </template>
    </Dialog>

    <!-- Diàleg afegir aula -->
    <Dialog
      v-model:visible="mostrarDialogAfegirAula"
      :header="$t('examConfig.rooms.addTitle')"
      :modal="true"
      :style="{ width: '400px' }"
    >
      <div class="p-fluid">
        <div class="field">
          <label>{{ $t('examConfig.rooms.codeLabel') }}</label>
          <InputText
            v-model="novaAula"
            :placeholder="$t('examConfig.rooms.codePlaceholder')"
            @keyup.enter="afegirAula"
          />
        </div>
      </div>

      <template #footer>
        <Button :label="$t('common.cancel')" @click="mostrarDialogAfegirAula = false" class="p-button-text" />
        <Button
          :label="$t('common.add')"
          @click="afegirAula"
          class="p-button-success"
          :disabled="!novaAula"
        />
      </template>
    </Dialog>

    <!-- Diàleg reanomenar item -->
    <Dialog
      v-model:visible="mostrarDialogRenomItem"
      :header="$t('common.edit')"
      :modal="true"
      :style="{ width: '400px' }"
    >
      <div class="p-fluid">
        <div class="field">
          <label>{{ $t('common.new') }}</label>
          <InputText
            v-model="renomValor"
            @keyup.enter="reanomenarItem"
            autofocus
          />
        </div>
      </div>

      <template #footer>
        <Button :label="$t('common.cancel')" @click="mostrarDialogRenomItem = false" class="p-button-text" />
        <Button
          :label="$t('common.save')"
          @click="reanomenarItem"
          class="p-button-success"
          :disabled="!renomValor || renomValor === itemEditant"
        />
      </template>
    </Dialog>

    <!-- Diàleg d'importació des de l'XML -->
    <Dialog
      v-model:visible="mostrarDialegImport"
      :header="$t('examConfig.import.title')"
      :modal="true"
      :style="{ width: '950px', maxHeight: '85vh' }"
    >
      <div v-if="carregantPropostes" class="loading">
        <i class="pi pi-spin pi-spinner" style="font-size: 2rem;"></i>
        <p>{{ $t('examConfig.import.loading') }}</p>
      </div>

      <div v-else>
        <Message severity="info" :closable="false">
          {{ $t('examConfig.import.helpText') }}
        </Message>

        <div class="filtres-import">
          <MultiSelect
            v-model="filtreNivellImport"
            :options="nivellsImport"
            :placeholder="$t('examConfig.assignments.filterLevel')"
            :selectedItemsLabel="$t('examConfig.import.levelsSelected', { count: filtreNivellImport.length })"
            :maxSelectedLabels="2"
            display="chip"
            class="filtre-dropdown"
          />
          <MultiSelect
            v-model="filtreAssignaturaImport"
            :options="assignaturesImport"
            :placeholder="$t('examConfig.assignments.filterSubject')"
            :selectedItemsLabel="$t('examConfig.import.subjectsSelected', { count: filtreAssignaturaImport.length })"
            :maxSelectedLabels="2"
            display="chip"
            :filter="true"
            class="filtre-dropdown"
          />
          <Dropdown
            v-model="filtreEstatImport"
            :options="[
              { value: '', label: $t('common.all') },
              { value: 'nova', label: $t('examConfig.import.newProposal') },
              { value: 'existent', label: $t('examConfig.import.alreadyExists') }
            ]"
            optionLabel="label" optionValue="value"
            :placeholder="$t('examConfig.import.status')"
            class="filtre-dropdown"
          />
        </div>

        <Tag severity="info" :value="$t('examConfig.import.selectedCount', {
          selected: propostesSeleccionades.length, total: propostes.length })" style="margin: 8px 0; display: inline-block;" />
        <Tag v-if="propostesFiltrades.length !== propostes.length" severity="secondary"
          :value="$t('examConfig.import.filteredCount', { count: propostesFiltrades.length })" style="margin: 8px 0 8px 6px; display: inline-block;" />

        <DataTable
          :value="propostesFiltrades"
          dataKey="_key"
          :paginator="true"
          :rows="15"
          :rowsPerPageOptions="[15, 30, 50, 100]"
          stripedRows
          showGridlines
          responsiveLayout="scroll"
          class="assignacions-table p-datatable-sm"
        >
          <Column style="width: 3rem">
            <template #header>
              <Checkbox
                :modelValue="dragSelectAssignacions.allSelected.value"
                @update:modelValue="dragSelectAssignacions.toggleAll"
                binary
              />
            </template>
            <template #body="slotProps">
              <Checkbox
                :modelValue="dragSelectAssignacions.isSelected(slotProps.data)"
                binary
                @mousedown.prevent="dragSelectAssignacions.onMouseDown(slotProps.data, $event)"
                @mouseenter="dragSelectAssignacions.onMouseEnter(slotProps.data)"
              />
            </template>
          </Column>
          <Column field="nivell" :header="$t('examConfig.tabs.levels')" sortable style="min-width: 100px" />
          <Column field="assignatura" :header="$t('common.subject')" sortable style="min-width: 180px">
            <template #editor="{ data, field }">
              <InputText v-model="data[field]" class="w-full p-inputtext-sm" />
            </template>
          </Column>
          <Column field="grup" :header="$t('common.group')" sortable style="min-width: 120px">
            <template #editor="{ data, field }">
              <InputText v-model="data[field]" class="w-full p-inputtext-sm" />
            </template>
          </Column>
          <Column field="titular" :header="$t('examConfig.assignments.owner')" sortable style="min-width: 150px" />
          <Column field="aula" :header="$t('common.room')" sortable style="min-width: 120px" />
          <Column field="ja_existeix" :header="$t('examConfig.import.status')" style="min-width: 110px">
            <template #body="slotProps">
              <Tag v-if="slotProps.data.ja_existeix" severity="secondary" :value="$t('examConfig.import.alreadyExists')" />
              <Tag v-else-if="slotProps.data.descartada" severity="warning" :value="$t('examConfig.import.previouslyDismissed')" />
              <Tag v-else severity="success" :value="$t('examConfig.import.newProposal')" />
            </template>
          </Column>
        </DataTable>
      </div>

      <template #footer>
        <div class="import-footer">
          <div class="overwrite-check">
            <Checkbox v-model="sobreescriuImportacio" inputId="overwrite-xml" binary />
            <label for="overwrite-xml">{{ $t('examConfig.import.overwrite') }}</label>
          </div>
          <div>
            <Button :label="$t('common.cancel')" @click="mostrarDialegImport = false" class="p-button-text" />
            <Button
              :label="$t('examConfig.import.confirmButton', { count: propostesSeleccionades.length })"
              icon="pi pi-check"
              @click="previsualitzarImportacio"
              class="p-button-success"
              :loading="calculantResumPrevi"
              :disabled="propostesSeleccionades.length === 0"
            />
          </div>
        </div>
      </template>
    </Dialog>

    <!-- Diàleg de resum PREVI (abans d'escriure res): cal confirmar o cancel·lar -->
    <Dialog
      v-model:visible="mostrarResumPrevi"
      :header="$t('examConfig.import.previewTitle')"
      :modal="true"
      :closable="false"
      :style="{ width: '600px', maxHeight: '85vh' }"
    >
      <div v-if="resumPrevi" class="resum-import">
        <Message severity="info" :closable="false">
          {{ $t('examConfig.import.previewHelp') }}
        </Message>

        <Message v-if="resumPreviSobreescriu" severity="warn" :closable="false">
          <div class="resum-avis-sobreescriu">
            <span>{{ $t('examConfig.import.overwriteBackupWarning') }}</span>
            <Button
              :label="$t('examConfig.import.downloadBackup')"
              icon="pi pi-download"
              size="small"
              class="p-button-outlined p-button-sm"
              @click="exportarAssignacionsCsv"
            />
          </div>
        </Message>

        <template v-for="secio in [
          { key: 'nivells_creats', label: $t('examConfig.tabs.levels') },
          { key: 'grups_creats', label: $t('common.group') },
          { key: 'assignatures_creades', label: $t('common.subject') },
          { key: 'aules_creades', label: $t('examConfig.tabs.rooms') },
          { key: 'assignacions_creades', label: $t('examConfig.tabs.assignments') },
        ]" :key="secio.key">
          <div v-if="resumPrevi[secio.key] && resumPrevi[secio.key].length" class="resum-seccio">
            <h4>{{ secio.label }} ({{ resumPrevi[secio.key].length }})</h4>
            <ul>
              <li v-for="(item, i) in resumPrevi[secio.key]" :key="i">{{ item }}</li>
            </ul>
          </div>
        </template>

        <p v-if="resumPrevi.ja_existien">
          {{ $t('examConfig.import.alreadyExistedCount', { count: resumPrevi.ja_existien }) }}
        </p>

        <Message
          v-if="resumPrevi.avisos && resumPrevi.avisos.length"
          severity="warn"
          :closable="false"
          class="resum-avisos"
        >
          <ul>
            <li v-for="(avis, i) in resumPrevi.avisos" :key="i">{{ avis }}</li>
          </ul>
        </Message>
      </div>

      <template #footer>
        <Button :label="$t('common.cancel')" @click="mostrarResumPrevi = false" class="p-button-text" />
        <Button
          :label="$t('examConfig.import.confirmImport')"
          icon="pi pi-check"
          @click="confirmarImportacioDefinitiva"
          class="p-button-success"
          :loading="important"
        />
      </template>
    </Dialog>

    <!-- Diàleg de resum FINAL (breu, després d'importar de veritat) -->
    <Dialog
      v-model:visible="mostrarResumFinal"
      :header="$t('examConfig.import.summaryTitle')"
      :modal="true"
      :closable="false"
      :style="{ width: '500px' }"
    >
      <div v-if="resumFinal">
        <p>{{ $t('examConfig.import.doneBrief', {
          nivells: resumFinal.nivells_creats.length,
          grups: resumFinal.grups_creats.length,
          assignatures: resumFinal.assignatures_creades.length,
          aules: resumFinal.aules_creades.length,
          assignacions: resumFinal.assignacions_creades.length,
        }) }}</p>
        <p v-if="resumFinal.ja_existien">
          {{ $t('examConfig.import.alreadyExistedCount', { count: resumFinal.ja_existien }) }}
        </p>
        <Message
          v-if="resumFinal.avisos && resumFinal.avisos.length"
          severity="warn"
          :closable="false"
          class="resum-avisos"
        >
          <ul>
            <li v-for="(avis, i) in resumFinal.avisos" :key="i">{{ avis }}</li>
          </ul>
        </Message>
      </div>

      <template #footer>
        <Button
          :label="$t('common.close')"
          icon="pi pi-times"
          @click="mostrarResumFinal = false"
          class="p-button-success"
        />
      </template>
    </Dialog>


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
import { ref, watch, computed, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import axios from 'axios'
import { useToast } from 'primevue/usetoast'
import { useConfirm } from 'primevue/useconfirm'
import Dialog from 'primevue/dialog'
import TabView from 'primevue/tabview'
import TabPanel from 'primevue/tabpanel'
import Dropdown from 'primevue/dropdown'
import MultiSelect from 'primevue/multiselect'
import InputText from 'primevue/inputtext'
import Button from 'primevue/button'
import Tag from 'primevue/tag'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Message from 'primevue/message'
import Checkbox from 'primevue/checkbox'

const toast = useToast()
const { t } = useI18n()
const confirm = useConfirm()

// Selecció múltiple per a taules de revisió d'importació: clic normal
// alterna una fila, Maj+clic selecciona el rang des de l'última clicada, i
// arrossegar amb el botó premut "pinta" seleccionar/deseleccionar per on
// passa el ratolí (mateix estat que la fila on ha començat l'arrossegament).
function useDragSelect(itemsRef, selectedRef) {
  // lastIndex es la POSICIÓ dins itemsRef.value (no un _key absolut), perquè
  // el rang de Maj+clic funcioni bé encara que itemsRef estigui filtrat.
  const lastIndex = ref(null)
  const dragging = ref(false)
  const dragValue = ref(true)

  const isSelected = (item) => selectedRef.value.some(s => s._key === item._key)

  const setSelected = (item, value) => {
    const ja = isSelected(item)
    if (value && !ja) selectedRef.value = [...selectedRef.value, item]
    else if (!value && ja) selectedRef.value = selectedRef.value.filter(s => s._key !== item._key)
  }

  const onMouseDown = (item, event) => {
    const idx = itemsRef.value.findIndex(i => i._key === item._key)
    const nouEstat = !isSelected(item)
    if (event.shiftKey && lastIndex.value !== null) {
      const [des, fins] = [lastIndex.value, idx].sort((a, b) => a - b)
      for (let i = des; i <= fins; i++) {
        setSelected(itemsRef.value[i], true)
      }
    } else {
      setSelected(item, nouEstat)
      dragValue.value = nouEstat
    }
    lastIndex.value = idx
    dragging.value = true
  }

  const onMouseEnter = (item) => {
    if (dragging.value) setSelected(item, dragValue.value)
  }

  const stopDragging = () => { dragging.value = false }

  onMounted(() => window.addEventListener('mouseup', stopDragging))
  onUnmounted(() => window.removeEventListener('mouseup', stopDragging))

  // "Selecciona/desselecciona tot" opera sobre itemsRef (passa-hi la llista
  // FILTRADA perquè només afecti el que es veu en aquell moment).
  const allSelected = computed(() => itemsRef.value.length > 0 && itemsRef.value.every(isSelected))
  const toggleAll = (value) => {
    if (value) {
      const nous = itemsRef.value.filter(i => !isSelected(i))
      selectedRef.value = [...selectedRef.value, ...nous]
    } else {
      const keys = new Set(itemsRef.value.map(i => i._key))
      selectedRef.value = selectedRef.value.filter(s => !keys.has(s._key))
    }
  }

  return { isSelected, onMouseDown, onMouseEnter, allSelected, toggleAll }
}

const props = defineProps({
  visible: {
    type: Boolean,
    required: true
  }
})

const emit = defineEmits(['update:visible'])

const loading = ref(false)
const nivells = ref([])
const xmlMissingNotified = ref(false)

// Edició i Renom
const itemEditant = ref(null)
const mostrarDialogRenomItem = ref(false)
const renomTipus = ref('') // 'nivell', 'assignatura', 'grup', 'aula'
const renomValor = ref('')

// Nivells
const mostrarDialogAfegirNivell = ref(false)
const nouNivell = ref('')

// Assignatures
const nivellSeleccionat = ref(null)
const assignatures = ref([])
const mostrarDialogAfegirAssignatura = ref(false)
const novaAssignatura = ref('')

// Grups
const nivellSeleccionatGrups = ref(null)
const grups = ref([])
const mostrarDialogAfegirGrup = ref(false)
const nouGrup = ref('')

// Aules
const aules = ref([])
const mostrarDialogAfegirAula = ref(false)
const novaAula = ref('')

// Assignacions Professor-Titular
const assignacions = ref([])
const assignacionsFiltrades = ref([])
const allLabel = computed(() => t('common.all'))
const filtreNivellAssignacions = ref(allLabel.value)
const filtreAssignaturaAssignacions = ref(allLabel.value)
const totesAssignatures = ref([])
const totsGrups = ref([])
const assignaturesUniques = ref([])
const professors = ref([])
const nextTempId = ref(-1)
const afinitats = ref([])

watch(allLabel, (newVal, oldVal) => {
  if (filtreNivellAssignacions.value === oldVal) {
    filtreNivellAssignacions.value = newVal
  }
  if (filtreAssignaturaAssignacions.value === oldVal) {
    filtreAssignaturaAssignacions.value = newVal
  }
})

const carregarNivells = async () => {
  try {
    const response = await axios.get('/api/config/nivells')
    nivells.value = response.data.nivells
  } catch (error) {
    console.error('Error carregant nivells:', error)
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: t('examConfig.errors.loadLevels'),
      life: 3000
    })
  }
}

const carregarAssignatures = async () => {
  if (!nivellSeleccionat.value) return

  try {
    const response = await axios.get(`/api/config/assignatures/${nivellSeleccionat.value}`)
    assignatures.value = response.data.assignatures
  } catch (error) {
    console.error('Error carregant assignatures:', error)
    assignatures.value = []
  }
}

// ===== FUNCIONS NIVELLS =====

const afegirNivell = async () => {
  if (!nouNivell.value) return

  try {
    await axios.post('/api/config/nivells', {
      codi: nouNivell.value.trim().toUpperCase(),
      nom: nouNivell.value.trim().toUpperCase()
    })

    toast.add({
      severity: 'success',
      summary: t('common.added'),
      detail: t('examConfig.levels.added'),
      life: 2000
    })

    nouNivell.value = ''
    mostrarDialogAfegirNivell.value = false
    await carregarNivells()
  } catch (error) {
    console.error('Error afegint nivell:', error)
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: error.response?.data?.detail || t('examConfig.errors.addLevel'),
      life: 3000
    })
  }
}

const eliminarNivell = async (codi) => {
  confirm.require({
    message: t('examConfig.levels.deleteConfirmMessage', { code: codi }),
    header: t('common.confirmation'),
    icon: 'pi pi-exclamation-triangle',
    acceptLabel: t('common.delete'),
    rejectLabel: t('common.cancel'),
    acceptClass: 'p-button-danger',
    accept: async () => {
      try {
        await axios.delete(`/api/config/nivells/${codi}`)

        toast.add({
          severity: 'success',
          summary: t('common.deleted'),
          detail: t('examConfig.levels.deleted'),
          life: 2000
        })

        await carregarNivells()
      } catch (error) {
        console.error('Error eliminant nivell:', error)
        toast.add({
          severity: 'error',
          summary: t('common.error'),
          detail: error.response?.data?.detail || t('examConfig.errors.deleteLevel'),
          life: 3000
        })
      }
    }
  })
}

// ===== FUNCIONS ASSIGNATURES =====

const afegirAssignatura = async () => {
  if (!novaAssignatura.value || !nivellSeleccionat.value) return

  try {
    await axios.post(`/api/config/assignatures/${nivellSeleccionat.value}`, {
      nom: novaAssignatura.value.trim().toUpperCase()
    })

    toast.add({
      severity: 'success',
      summary: t('common.added'),
      detail: t('examConfig.subjects.added'),
      life: 2000
    })

    novaAssignatura.value = ''
    mostrarDialogAfegirAssignatura.value = false
    await carregarAssignatures()
  } catch (error) {
    console.error('Error afegint assignatura:', error)
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: error.response?.data?.detail || t('examConfig.errors.addSubject'),
      life: 3000
    })
  }
}

const eliminarAssignatura = async (nom) => {
  confirm.require({
    message: t('examConfig.subjects.deleteConfirmMessage', { name: nom }),
    header: t('common.confirmDelete'),
    icon: 'pi pi-exclamation-triangle',
    acceptLabel: t('common.delete'),
    rejectLabel: t('common.cancel'),
    accept: async () => {
      try {
        await axios.delete(`/api/config/assignatures/${nivellSeleccionat.value}/${encodeURIComponent(nom)}`)

        toast.add({
          severity: 'success',
          summary: t('common.deleted'),
          detail: t('examConfig.subjects.deleted'),
          life: 2000
        })

        await carregarAssignatures()
      } catch (error) {
        console.error('Error eliminant assignatura:', error)
        toast.add({
          severity: 'error',
          summary: t('common.error'),
          detail: t('examConfig.errors.deleteSubject'),
          life: 3000
        })
      }
    }
  })
}

const carregarGrups = async () => {
  if (!nivellSeleccionatGrups.value) return

  try {
    const response = await axios.get(`/api/config/grups/${nivellSeleccionatGrups.value}`)
    grups.value = response.data.grups
  } catch (error) {
    console.error('Error carregant grups:', error)
    grups.value = []
  }
}

const afegirGrup = async () => {
  if (!nouGrup.value || !nivellSeleccionatGrups.value) return

  try {
    await axios.post(`/api/config/grups/${nivellSeleccionatGrups.value}`, {
      codi: nouGrup.value.trim()
    })

    toast.add({
      severity: 'success',
      summary: t('common.added'),
      detail: t('examConfig.groups.added'),
      life: 2000
    })

    nouGrup.value = ''
    mostrarDialogAfegirGrup.value = false
    await carregarGrups()
  } catch (error) {
    console.error('Error afegint grup:', error)
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: error.response?.data?.detail || t('examConfig.errors.addGroup'),
      life: 3000
    })
  }
}

const eliminarGrup = async (codi) => {
  confirm.require({
    message: t('examConfig.groups.deleteConfirmMessage', { code: codi }),
    header: t('common.confirmDelete'),
    icon: 'pi pi-exclamation-triangle',
    acceptLabel: t('common.delete'),
    rejectLabel: t('common.cancel'),
    accept: async () => {
      try {
        await axios.delete(`/api/config/grups/${encodeURIComponent(codi)}`)

        toast.add({
          severity: 'success',
          summary: t('common.deleted'),
          detail: t('examConfig.groups.deleted'),
          life: 2000
        })

        await carregarGrups()
      } catch (error) {
        console.error('Error eliminant grup:', error)
        toast.add({
          severity: 'error',
          summary: t('common.error'),
          detail: t('examConfig.errors.deleteGroup'),
          life: 3000
        })
      }
    }
  })
}

const carregarAules = async () => {
  try {
    const response = await axios.get('/api/config/aules')
    aules.value = response.data.aules
  } catch (error) {
    console.error('Error carregant aules:', error)
    aules.value = []
  }
}

const afegirAula = async () => {
  if (!novaAula.value) return

  try {
    await axios.post('/api/config/aules', {
      codi: novaAula.value.trim()
    })

    toast.add({
      severity: 'success',
      summary: t('common.added'),
      detail: t('examConfig.rooms.added'),
      life: 2000
    })

    novaAula.value = ''
    mostrarDialogAfegirAula.value = false
    await carregarAules()
  } catch (error) {
    console.error('Error afegint aula:', error)
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: error.response?.data?.detail || t('examConfig.errors.addRoom'),
      life: 3000
    })
  }
}

const eliminarAula = async (codi) => {
  confirm.require({
    message: t('examConfig.rooms.deleteConfirmMessage', { code: codi }),
    header: t('common.confirmDelete'),
    icon: 'pi pi-exclamation-triangle',
    acceptLabel: t('common.delete'),
    rejectLabel: t('common.cancel'),
    accept: async () => {
      try {
        await axios.delete(`/api/config/aules/${encodeURIComponent(codi)}`)

        toast.add({
          severity: 'success',
          summary: t('common.deleted'),
          detail: t('examConfig.rooms.deleted'),
          life: 2000
        })

        await carregarAules()
      } catch (error) {
        console.error('Error eliminant aula:', error)
        toast.add({
          severity: 'error',
          summary: t('common.error'),
          detail: t('examConfig.errors.deleteRoom'),
          life: 3000
        })
      }
    }
  })
}

const carregarTotesAssignatures = async () => {
  // Carregar totes les assignatures de tots els nivells
  const assignaturesSet = new Set()
  for (const nivell of nivells.value) {
    try {
      const response = await axios.get(`/api/config/assignatures/${nivell}`)
      response.data.assignatures.forEach(a => assignaturesSet.add(a))
    } catch (error) {
      console.error(`Error carregant assignatures de ${nivell}:`, error)
    }
  }
  totesAssignatures.value = Array.from(assignaturesSet).sort()
}

const carregarTotsGrups = async () => {
  // Carregar tots els grups de tots els nivells
  const grupsSet = new Set()
  for (const nivell of nivells.value) {
    try {
      const response = await axios.get(`/api/config/grups/${nivell}`)
      response.data.grups.forEach(g => grupsSet.add(g))
    } catch (error) {
      console.error(`Error carregant grups de ${nivell}:`, error)
    }
  }
  totsGrups.value = Array.from(grupsSet).sort()
}

const carregarProfessors = async () => {
  try {
    const response = await axios.get('/api/professors')
    if (response.data?.xml_missing && !xmlMissingNotified.value) {
      toast.add({
        severity: 'warn',
        summary: t('common.warning'),
        detail: t('common.xmlMissing'),
        life: 4000
      })
      xmlMissingNotified.value = true
    }
    professors.value = response.data.professors
  } catch (error) {
    console.error('Error carregant professors:', error)
    professors.value = []
  }
}

const carregarAssignacions = async () => {
  try {
    const response = await axios.get('/api/config/assignacions')
    assignacions.value = response.data.assignacions

    // Extreure assignatures úniques
    const assignaturesSet = new Set(assignacions.value.map(a => a.assignatura))
    assignaturesUniques.value = Array.from(assignaturesSet).sort()

    filtrarAssignacions()
  } catch (error) {
    console.error('Error carregant assignacions:', error)
    assignacions.value = []
  }
}

const filtrarAssignacions = () => {
  let filtrades = [...assignacions.value]

  // Filtrar per nivell (hem de buscar quins grups pertanyen al nivell)
  if (filtreNivellAssignacions.value && filtreNivellAssignacions.value !== allLabel.value) {
    filtrades = filtrades.filter(a => {
      // Comprovar si el grup comença amb el nivell
      return a.grup.startsWith(filtreNivellAssignacions.value)
    })
  }

  // Filtrar per assignatura
  if (filtreAssignaturaAssignacions.value && filtreAssignaturaAssignacions.value !== allLabel.value) {
    filtrades = filtrades.filter(a => a.assignatura === filtreAssignaturaAssignacions.value)
  }

  assignacionsFiltrades.value = filtrades
}

const afegirFilaAssignacio = () => {
  // Afegir fila temporal amb id negatiu
  const novaFila = {
    id: nextTempId.value--,
    assignatura: '',
    grup: '',
    titular: '',
    aula: '',
    _isNew: true
  }
  assignacions.value.unshift(novaFila)
  filtrarAssignacions()
}

const onCellEditComplete = async (event) => {
  const { data, newValue, field } = event

  // Actualitzar valor
  data[field] = newValue

  // Si és una fila nova i té assignatura + grup, crear-la
  if (data._isNew && data.assignatura && data.grup) {
    try {
      const response = await axios.post('/api/config/assignacions', {
        assignatura: data.assignatura,
        grup: data.grup,
        titular: data.titular || '',
        aula: data.aula || ''
      })

      // Substituir id temporal per id real
      data.id = response.data.id
      delete data._isNew

      toast.add({
        severity: 'success',
        summary: t('common.created'),
        detail: t('examConfig.assignments.created'),
        life: 2000
      })

      // NO recarreguem - ja tenim les dades actualitzades localment
      filtrarAssignacions()
    } catch (error) {
      console.error('Error creant assignació:', error)
      toast.add({
        severity: 'error',
        summary: t('common.error'),
        detail: error.response?.data?.detail || t('examConfig.errors.createAssignment'),
        life: 3000
      })
    }
  }
  // Si és una fila existent, actualitzar-la
  else if (!data._isNew && data.id > 0) {
    try {
      await axios.put(`/api/config/assignacions/${data.id}`, {
        titular: data.titular || '',
        aula: data.aula || ''
      })

      toast.add({
        severity: 'success',
        summary: t('common.updated'),
        detail: t('examConfig.assignments.updated'),
        life: 1500
      })
    } catch (error) {
      console.error('Error actualitzant assignació:', error)
      toast.add({
        severity: 'error',
        summary: t('common.error'),
        detail: t('examConfig.errors.updateAssignment'),
        life: 3000
      })
    }
  }
}

const eliminarAssignacio = async (id) => {
  // Si és una fila nova local (id negatiu), eliminar directament sense API
  if (id < 0) {
    assignacions.value = assignacions.value.filter(a => a.id !== id)
    filtrarAssignacions()
    return
  }

  confirm.require({
    message: t('examConfig.assignments.deleteConfirmMessage'),
    header: t('common.confirmDelete'),
    icon: 'pi pi-exclamation-triangle',
    acceptLabel: t('common.delete'),
    rejectLabel: t('common.cancel'),
    accept: async () => {
      try {
        await axios.delete(`/api/config/assignacions/${id}`)

        toast.add({
          severity: 'success',
          summary: t('common.deleted'),
          detail: t('examConfig.assignments.deleted'),
          life: 2000
        })

        await carregarAssignacions()
      } catch (error) {
        console.error('Error eliminant assignació:', error)
        toast.add({
          severity: 'error',
          summary: t('common.error'),
          detail: t('examConfig.errors.deleteAssignment'),
          life: 3000
        })
      }
    }
  })
}

// ===== Eliminació massiva (netejar abans de re-importar) =====

const eliminarAssignacionsFiltrades = () => {
  if (assignacionsFiltrades.value.length === 0) return

  confirm.require({
    message: t('examConfig.assignments.deleteFilteredConfirmMessage', { count: assignacionsFiltrades.value.length }),
    header: t('common.confirmDelete'),
    icon: 'pi pi-exclamation-triangle',
    acceptLabel: t('common.delete'),
    rejectLabel: t('common.cancel'),
    accept: async () => {
      try {
        const ids = assignacionsFiltrades.value.filter(a => a.id > 0).map(a => a.id)
        await axios.delete('/api/config/assignacions', { data: { ids } })
        toast.add({ severity: 'success', summary: t('common.deleted'), detail: t('examConfig.assignments.deleted'), life: 2000 })
        await carregarAssignacions()
      } catch (error) {
        console.error('Error eliminant assignacions:', error)
        toast.add({ severity: 'error', summary: t('common.error'), detail: t('examConfig.errors.deleteAssignment'), life: 3000 })
      }
    }
  })
}

const eliminarTotesAssignacions = () => {
  if (assignacions.value.length === 0) return

  confirm.require({
    message: t('examConfig.assignments.deleteAllConfirmMessage', { count: assignacions.value.length }),
    header: t('common.confirmDelete'),
    icon: 'pi pi-exclamation-triangle',
    acceptLabel: t('common.delete'),
    rejectLabel: t('common.cancel'),
    accept: async () => {
      try {
        await axios.delete('/api/config/assignacions', { data: { tot: true } })
        toast.add({ severity: 'success', summary: t('common.deleted'), detail: t('examConfig.assignments.deleted'), life: 2000 })
        await carregarAssignacions()
      } catch (error) {
        console.error('Error eliminant totes les assignacions:', error)
        toast.add({ severity: 'error', summary: t('common.error'), detail: t('examConfig.errors.deleteAssignment'), life: 3000 })
      }
    }
  })
}

// ===== Importar des de l'XML =====

const mostrarDialegImport = ref(false)
const carregantPropostes = ref(false)
const propostes = ref([])
const propostesSeleccionades = ref([])
const important = ref(false)
const sobreescriuImportacio = ref(false)

const filtreNivellImport = ref([])
const filtreAssignaturaImport = ref([])
const filtreEstatImport = ref('')

const nivellsImport = computed(() => [...new Set(propostes.value.map(p => p.nivell))].sort())
const assignaturesImport = computed(() => [...new Set(propostes.value.map(p => p.assignatura))].sort())

const propostesFiltrades = computed(() => propostes.value.filter(p =>
  (filtreNivellImport.value.length === 0 || filtreNivellImport.value.includes(p.nivell)) &&
  (filtreAssignaturaImport.value.length === 0 || filtreAssignaturaImport.value.includes(p.assignatura)) &&
  (!filtreEstatImport.value ||
    (filtreEstatImport.value === 'nova' && !p.ja_existeix) ||
    (filtreEstatImport.value === 'existent' && p.ja_existeix))
))

const dragSelectAssignacions = useDragSelect(propostesFiltrades, propostesSeleccionades)

const obrirImportacio = async () => {
  mostrarDialegImport.value = true
  carregantPropostes.value = true
  propostes.value = []
  propostesSeleccionades.value = []
  filtreNivellImport.value = []
  filtreAssignaturaImport.value = []
  filtreEstatImport.value = ''
  try {
    const { data } = await axios.get('/api/config/importar-assignacions/preview')
    propostes.value = (data.propostes || []).map((p, idx) => ({ ...p, _key: idx }))
    // Pre-selecciona només les que encara no existeixen i que no s'havien
    // descartat expressament en una importació anterior
    propostesSeleccionades.value = propostes.value.filter(p => !p.ja_existeix && !p.descartada)
  } catch (error) {
    console.error('Error generant propostes d\'importació:', error)
    toast.add({ severity: 'error', summary: t('common.error'), detail: t('examConfig.import.errorPreview'), life: 3000 })
    mostrarDialegImport.value = false
  } finally {
    carregantPropostes.value = false
  }
}

// ===== Resum previ (dry-run) i confirmació final (compartit entre XML i CSV) =====

const mostrarResumPrevi = ref(false)
const resumPrevi = ref(null)
const resumPreviSobreescriu = ref(false)
const calculantResumPrevi = ref(false)
const mostrarResumFinal = ref(false)
const resumFinal = ref(null)
const origenResumPrevi = ref('xml') // 'xml' | 'csv'
const fitxerCsvPendent = ref(null)
const overwriteCsvPendent = ref(false)

const netejaProposta = ({ _key, ja_existeix, descartada, ...rest }) => rest

const previsualitzarImportacio = async () => {
  if (propostesSeleccionades.value.length === 0) return
  calculantResumPrevi.value = true
  try {
    const { data } = await axios.post('/api/config/importar-assignacions/dry-run', {
      propostes: propostesSeleccionades.value.map(netejaProposta),
      overwrite: sobreescriuImportacio.value
    })
    origenResumPrevi.value = 'xml'
    resumPreviSobreescriu.value = sobreescriuImportacio.value
    resumPrevi.value = data
    mostrarResumPrevi.value = true
  } catch (error) {
    console.error('Error calculant el resum previ:', error)
    toast.add({ severity: 'error', summary: t('common.error'), detail: t('examConfig.import.errorPreview'), life: 3000 })
  } finally {
    calculantResumPrevi.value = false
  }
}

const previsualitzarImportacioCsv = async (fitxer, overwrite) => {
  const formData = new FormData()
  formData.append('file', fitxer)
  formData.append('overwrite', overwrite)
  try {
    const { data } = await axios.post('/api/config/importar-assignacions-csv/dry-run', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    origenResumPrevi.value = 'csv'
    resumPreviSobreescriu.value = overwrite
    fitxerCsvPendent.value = fitxer
    overwriteCsvPendent.value = overwrite
    resumPrevi.value = data
    mostrarResumPrevi.value = true
  } catch (error) {
    console.error('Error calculant el resum previ del CSV:', error)
    const detail = error.response?.data?.detail || t('examConfig.import.errorPreview')
    toast.add({ severity: 'error', summary: t('common.error'), detail, life: 4000 })
  }
}

const confirmarImportacioDefinitiva = async () => {
  important.value = true
  try {
    let data
    if (origenResumPrevi.value === 'csv') {
      const formData = new FormData()
      formData.append('file', fitxerCsvPendent.value)
      formData.append('overwrite', overwriteCsvPendent.value)
      const resposta = await axios.post('/api/config/importar-assignacions-csv', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      })
      data = resposta.data
      fitxerCsvPendent.value = null
    } else {
      const seleccionadesKeys = new Set(propostesSeleccionades.value.map(p => p._key))
      const descartades = propostes.value
        .filter(p => !seleccionadesKeys.has(p._key) && !p.ja_existeix)
        .map(({ assignatura, grup, titular }) => ({ assignatura, grup, titular }))

      const resposta = await axios.post('/api/config/importar-assignacions', {
        propostes: propostesSeleccionades.value.map(netejaProposta),
        descartades,
        overwrite: sobreescriuImportacio.value
      })
      data = resposta.data
      mostrarDialegImport.value = false
      sobreescriuImportacio.value = false
    }

    mostrarResumPrevi.value = false
    resumFinal.value = data
    mostrarResumFinal.value = true
    await carregarAssignacions()
  } catch (error) {
    console.error('Error important:', error)
    const detail = error.response?.data?.detail || t('examConfig.import.errorApply')
    toast.add({ severity: 'error', summary: t('common.error'), detail, life: 4000 })
  } finally {
    important.value = false
  }
}

// ===== Exportar / Importar assignacions en CSV =====

const inputCsvRef = ref(null)

const exportarAssignacionsCsv = () => {
  window.open('/api/config/exportar-assignacions-csv', '_blank')
}

const triarFitxerCsv = () => {
  inputCsvRef.value?.click()
}

const onFitxerCsvSeleccionat = (event) => {
  const fitxer = event.target.files?.[0]
  event.target.value = ''
  if (!fitxer) return

  confirm.require({
    message: t('examConfig.import.overwriteConfirmCsv', { filename: fitxer.name }),
    header: t('examConfig.import.importCsv'),
    icon: 'pi pi-question-circle',
    acceptLabel: t('examConfig.import.overwrite'),
    rejectLabel: t('examConfig.import.merge'),
    accept: () => previsualitzarImportacioCsv(fitxer, true),
    reject: () => previsualitzarImportacioCsv(fitxer, false)
  })
}

const carregarAfinitats = async () => {
  try {
    const response = await axios.get('/api/config/afinitats')
    const rows = Array.isArray(response.data?.afinitats) ? response.data.afinitats : []
    afinitats.value = rows.map((row) => ({
      base: row.base || '',
      ordreText: Array.isArray(row.ordre) ? row.ordre.join(',') : ''
    }))
  } catch (error) {
    console.error('Error carregant afinitats:', error)
    afinitats.value = []
  }
}

const afegirFilaAfinitat = () => {
  afinitats.value.push({ base: '', ordreText: '' })
}

const eliminarFilaAfinitat = (index) => {
  afinitats.value.splice(index, 1)
}

const desarAfinitats = async () => {
  const payload = afinitats.value
    .map((row) => ({
      base: (row.base || '').trim(),
      ordre: (row.ordreText || '')
        .split(',')
        .map((x) => x.trim())
        .filter(Boolean)
    }))
    .filter((row) => row.base)

  try {
    const response = await axios.put('/api/config/afinitats', { afinitats: payload })
    const saved = Array.isArray(response.data?.afinitats) ? response.data.afinitats : payload
    afinitats.value = saved.map((row) => ({
      base: row.base || '',
      ordreText: Array.isArray(row.ordre) ? row.ordre.join(',') : ''
    }))

    toast.add({
      severity: 'success',
      summary: t('common.saved'),
      detail: t('examConfig.affinities.saved'),
      life: 2000
    })
  } catch (error) {
    console.error('Error desant afinitats:', error)
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: error.response?.data?.detail || t('examConfig.errors.saveAffinities'),
      life: 3000
    })
  }
}

// ===== FUNCIONS REANOMENAR ITEM (PROPAGACIÓ) =====

const prepararRenomNivell = (codi) => {
  itemEditant.value = codi
  renomValor.value = codi
  renomTipus.value = 'nivell'
  mostrarDialogRenomItem.value = true
}

const prepararRenomAssignatura = (nom) => {
  itemEditant.value = nom
  renomValor.value = nom
  renomTipus.value = 'assignatura'
  mostrarDialogRenomItem.value = true
}

const prepararRenomGrup = (codi) => {
  itemEditant.value = codi
  renomValor.value = codi
  renomTipus.value = 'grup'
  mostrarDialogRenomItem.value = true
}

const prepararRenomAula = (codi) => {
  itemEditant.value = codi
  renomValor.value = codi
  renomTipus.value = 'aula'
  mostrarDialogRenomItem.value = true
}

const reanomenarItem = async () => {
  const antic = itemEditant.value
  const nou = renomValor.value.trim()

  if (!nou || antic === nou) {
    mostrarDialogRenomItem.value = false
    return
  }

  try {
    let url = ''
    let payload = {}

    if (renomTipus.value === 'nivell') {
      url = `/api/config/nivells/${antic}`
      payload = { nou_codi: nou }
    } else if (renomTipus.value === 'assignatura') {
      url = `/api/config/assignatures/${nivellSeleccionat.value}/${encodeURIComponent(antic)}`
      payload = { nou_nom: nou }
    } else if (renomTipus.value === 'grup') {
      url = `/api/config/grups/${encodeURIComponent(antic)}`
      payload = { nou_nom: nou }
    } else if (renomTipus.value === 'aula') {
      url = `/api/config/aules/${encodeURIComponent(antic)}`
      payload = { nou_nom: nou }
    }

    await axios.put(url, payload)

    toast.add({
      severity: 'success',
      summary: t('common.updated'),
      detail: t('common.updated'),
      life: 2000
    })

    // Propagació local a Assignacions per evitar recàrrega lenta
    assignacions.value.forEach(a => {
      if (renomTipus.value === 'assignatura' && a.assignatura === antic) {
        a.assignatura = nou
      } else if (renomTipus.value === 'grup' && a.grup === antic) {
        a.grup = nou
      } else if (renomTipus.value === 'aula' && a.aula === antic) {
        a.aula = nou
      }
    })

    // Recarregar la llista específica
    if (renomTipus.value === 'nivell') await carregarNivells()
    else if (renomTipus.value === 'assignatura') await carregarAssignatures()
    else if (renomTipus.value === 'grup') await carregarGrups()
    else if (renomTipus.value === 'aula') await carregarAules()

    // Recarregar també les llistes auxiliars dels dropdowns
    await carregarTotesAssignatures()
    await carregarTotsGrups()
    
    // Recarregar assignacions per actualitzar els filtres (assignaturesUniques)
    await carregarAssignacions()

    filtrarAssignacions()
    mostrarDialogRenomItem.value = false
  } catch (error) {
    console.error('Error reanomenant:', error)
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: error.response?.data?.detail || t('common.error'),
      life: 3000
    })
  }
}

const carregarTot = async () => {
  loading.value = true
  try {
    await carregarNivells()
    await carregarAules()
    await carregarTotesAssignatures()
    await carregarTotsGrups()
    await carregarProfessors()
    await carregarAssignacions()
    await carregarAfinitats()
  } catch (error) {
    console.error('Error carregant configuració:', error)
  } finally {
    loading.value = false
  }
}

const tancar = () => {
  emit('update:visible', false)
}

// Carregar quan s'obre el diàleg
watch(() => props.visible, (newVal) => {
  if (newVal) {
    carregarTot()
  }
})
</script>

<style scoped>
.resum-avis-sobreescriu {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  flex-wrap: wrap;
}

.loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 3rem 2rem;
  text-align: center;
  gap: 1rem;
  color: #667eea;
}

.config-container {
  padding: 0.75rem 0.75rem 0.5rem;
}

.tab-content {
  padding: 1rem 0;
  min-height: 400px;
}

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;
  gap: 1rem;
}

.toolbar-left {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.nivell-selector {
  min-width: 200px;
}

.items-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
  gap: 0.75rem;
  max-height: 450px;
  overflow-y: auto;
  padding: 0.5rem;
}

.item-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.75rem 1rem;
  background: #f9fafb;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  transition: all 0.2s;
}

.item-card:hover {
  background: #f3f4f6;
  border-color: #d1d5db;
  transform: translateY(-1px);
  box-shadow: 0 2px 4px rgba(0,0,0,0.05);
}

.item-name {
  font-weight: 500;
  color: #374151;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.empty-message {
  grid-column: 1 / -1;
  text-align: center;
  padding: 3rem 1rem;
  color: #9ca3af;
  font-style: italic;
}

.select-nivell-message {
  text-align: center;
  padding: 3rem 1rem;
  color: #6b7280;
  font-size: 1.1rem;
}

.field {
  margin-bottom: 1rem;
}

.field label {
  display: block;
  margin-bottom: 0.5rem;
  font-weight: 500;
  color: #374151;
}

/* Tab content amb taula */
.tab-content-table {
  padding: 1rem 0;
}

/* Estils per Assignacions DataTable */
.assignacions-table {
  margin-top: 1rem;
}

.import-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.overwrite-check {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.accions-buttons {
  display: flex;
  gap: 0.25rem;
  justify-content: center;
}

/* Estils per tab de Nivells */
.item-card-readonly {
  cursor: default;
}

.item-card-readonly:hover {
  transform: none;
}

.import-section {
  margin-top: 1.5rem;
  padding: 1.25rem;
  background: #f9fafb;
  border-radius: 8px;
}

.import-section h4 {
  margin: 0 0 0.5rem 0;
  color: #111827;
}

.import-section-desc {
  margin: 0 0 1rem 0;
  color: #4b5563;
  font-size: 0.9rem;
}

.import-buttons-row {
  display: flex;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.info-text {
  margin-top: 1.5rem;
  padding: 1rem;
  background: #eff6ff;
  border-left: 4px solid #3b82f6;
  border-radius: 4px;
  color: #1e40af;
  font-size: 0.9rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.field-hint {
  display: block;
  margin-top: 0.35rem;
  color: #6b7280;
  font-size: 0.85rem;
  font-style: italic;
}

/* Filtres assignacions */
.filtres-assignacions {
  display: flex;
  gap: 1rem;
  align-items: flex-end;
  margin-bottom: 1rem;
  padding: 1rem;
  background: #f9fafb;
  border-radius: 8px;
  flex-wrap: wrap;
}

.filtre-group {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.filtre-group label {
  font-weight: 500;
  color: #374151;
  font-size: 0.9rem;
}

.filtre-dropdown {
  min-width: 180px;
}

.filtres-import {
  display: flex;
  gap: 0.75rem;
  flex-wrap: wrap;
  margin-bottom: 0.5rem;
}

.toolbar-right {
  margin-left: auto;
  display: flex;
  gap: 0.5rem;
  align-items: center;
}

/* Taula inline editable */
:deep(.p-datatable-sm .p-datatable-tbody > tr > td) {
  padding: 0.4rem 0.5rem;
}

/* Dropdowns a les cel·les */
:deep(.p-datatable .p-datatable-tbody > tr > td .p-dropdown) {
  width: 100%;
  min-height: 32px;
}

:deep(.p-datatable .p-datatable-tbody > tr > td .p-dropdown .p-dropdown-label) {
  padding: 0.4rem 0.6rem;
  font-size: 0.9rem;
}

:deep(.p-datatable .p-datatable-tbody > tr > td .p-dropdown .p-dropdown-trigger) {
  width: 2rem;
}

/* Cel·les en mode edició - fons diferent */
:deep(.p-datatable .p-datatable-tbody > tr > td.p-cell-editing) {
  background-color: #fff3cd !important;
  padding: 0.2rem !important;
}

/* Hover a les cel·les editables */
:deep(.p-datatable .p-datatable-tbody > tr > td:not(:last-child):hover) {
  background-color: #f8f9fa;
  cursor: pointer;
}

.w-full {
  width: 100%;
}
</style>
