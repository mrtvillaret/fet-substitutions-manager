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
    <div v-if="loading" class="loading">
      <i class="pi pi-spin pi-spinner" style="font-size: 2rem;"></i>
      <p>{{ $t('common.loadingConfig') }}</p>
    </div>

    <div v-else class="config-container">
      <TabView class="app-tabview app-tabview--dialog">
        <!-- TAB 1: SISTEMA I FITXERS -->
        <TabPanel>
          <template #header>
            <span class="tab-header-lines">
              <span>{{ $t('config.tabs.systemLine1') }}</span>
              <span>{{ $t('config.tabs.systemLine2') }}</span>
            </span>
          </template>
          <div class="tab-content">
          <!-- Institucio i idioma -->
          <div v-if="isSuperAdmin" class="field">
            <label for="institucio">{{ $t('config.system.institutionCode') }}</label>
            <InputText
              id="institucio"
              v-model="settings.institucio"
              :placeholder="$t('config.system.institutionPlaceholder')"
              class="w-full logo-field"
              readonly
              disabled
            />
            <small class="field-hint">{{ $t('config.system.institutionCodeHint') }}</small>
          </div>

          <div class="field">
            <label for="institucio_display">{{ $t('config.system.institutionName') }}</label>
            <InputText
              id="institucio_display"
              v-model="settings.institucio_display_name"
              :placeholder="$t('config.system.institutionNamePlaceholder')"
              class="w-full logo-field"
              :disabled="!isSuperAdmin"
            />
            <small class="field-hint">{{ $t('config.system.institutionNameHint') }}</small>
          </div>

          <div class="field">
            <label for="logo">{{ $t('config.system.logoLabel') }}</label>
            <div class="p-inputgroup logo-inputgroup uniform-inputgroup">
              <InputText
                id="logo"
                v-model="logoNom"
                :placeholder="$t('config.system.logoPlaceholder')"
                readonly
                class="w-full logo-field"
              />
              <Button icon="pi pi-upload" @click="$refs.logoInput.click()" v-tooltip.top="$t('common.upload')" class="logo-upload-btn" />
            </div>
            <input
              ref="logoInput"
              type="file"
              accept=".png,.jpg,.jpeg"
              style="display: none"
              @change="pujarLogo"
            />
            <div v-if="logoUrl" class="logo-preview">
              <img :src="logoUrl" :alt="$t('config.system.logoAlt')" />
            </div>
            <small class="field-hint">{{ $t('config.system.logoHint') }}</small>
          </div>

          <div class="field">
            <label for="idioma">{{ $t('config.system.language') }}</label>
            <Dropdown
              id="idioma"
              v-model="settings.idioma"
              :options="idiomes"
              optionLabel="name"
              optionValue="code"
              :placeholder="$t('config.system.languagePlaceholder')"
              class="w-full logo-field"
            />
          </div>

          <Divider />

          <!-- Fitxer XML -->
          <div class="field">
            <label for="xml_path">{{ $t('config.system.xmlLabel') }}</label>
            <div class="p-inputgroup uniform-inputgroup">
              <InputText
                id="xml_path"
                v-model="settings.xml_horari_path"
                :placeholder="$t('config.system.xmlPlaceholder')"
                readonly
                class="w-full"
              />
              <Button icon="pi pi-upload" @click="$refs.fileInput.click()" v-tooltip.top="$t('config.system.xmlUpload')" />
            </div>
            <input
              ref="fileInput"
              type="file"
              accept=".xml"
              style="display: none"
              @change="pujarXML"
            />
            <small class="field-hint">{{ $t('config.system.xmlHint') }}</small>

            <!-- Avís: un curs arrencaria amb l'horari del curs anterior -->
            <div
              v-for="avis in avisosXml"
              :key="avis.curs_id"
              class="xml-avis-desync"
            >
              <i class="pi pi-exclamation-triangle" aria-hidden="true"></i>
              <div class="xml-avis-text">
                {{ $t('config.system.xmlCourseDesync', {
                  curs: avis.curs_nom,
                  inici: avis.curs_inici,
                  xmlInici: avis.xml_inici
                }) }}
              </div>
              <Button
                :label="$t('config.system.xmlFixDesync')"
                class="p-button-sm p-button-warning"
                @click="xmlVigentDesDe = parseIsoDate(avis.curs_inici)"
              />
            </div>

            <!-- Data de vigència: permet PREPARAR l'horari d'un curs futur -->
            <div class="xml-vigencia">
              <label class="date-inline-label">{{ $t('config.system.xmlEffectiveFrom') }}:</label>
              <Calendar
                v-model="xmlVigentDesDe"
                dateFormat="yy-mm-dd"
                :showIcon="true"
                :showButtonBar="true"
                class="xml-date"
              />
              <Button
                v-if="cursFuturSuggerit"
                :label="$t('config.system.xmlUseCourseStart', { nom: cursFuturSuggerit.nom })"
                class="p-button-text p-button-sm"
                @click="xmlVigentDesDe = parseIsoDate(cursFuturSuggerit.data_inici)"
              />
            </div>
            <small class="field-hint">{{ $t('config.system.xmlEffectiveHint') }}</small>
          </div>

          <!-- Versions XML -->
          <div class="field">
            <div class="toolbar" style="margin-bottom: 0.5rem;">
              <label>{{ $t('config.system.xmlVersions') }}</label>
              <Button
                icon="pi pi-refresh"
                @click="carregarXmlVersions"
                size="small"
                class="p-button-secondary"
                v-tooltip.top="$t('common.reload')"
              />
            </div>

            <div v-if="xmlVersionsLoading" class="loading-inline">
              <i class="pi pi-spin pi-spinner" />
              <span>{{ $t('common.loading') }}</span>
            </div>

            <div v-else-if="xmlVersions.length === 0" class="empty-inline">
              {{ $t('config.system.noXmlVersions') }}
            </div>

            <div v-else class="xml-versions">
              <div v-for="version in xmlVersionsDisplay" :key="version.id" class="xml-version-card">
                <div class="xml-version-header">
                  <span class="xml-path">{{ version.path }}</span>
                  <span v-if="!version.data_fi" class="xml-current">
                    {{ $t('config.system.xmlCurrent') }}
                  </span>
                </div>

                <div class="xml-version-row">
                  <div class="xml-version-dates">
                    <div class="date-field">
                      <label class="date-inline-label">{{ $t('config.system.xmlStart') }}:</label>
                      <Calendar
                        :modelValue="parseIsoDate(version.data_inici)"
                        @update:modelValue="value => { version.data_inici = formatIsoDate(value) }"
                        dateFormat="yy-mm-dd"
                        :showIcon="true"
                        class="xml-date"
                      />
                    </div>
                    <div class="date-field">
                      <label class="date-inline-label">{{ $t('config.system.xmlEnd') }}:</label>
                      <Calendar
                        :modelValue="parseIsoDate(version.data_fi)"
                        dateFormat="yy-mm-dd"
                        :showIcon="true"
                        class="xml-date"
                        :disabled="true"
                      />
                    </div>
                  </div>

                  <div class="xml-version-actions">
                    <Button
                      icon="pi pi-save"
                      :label="$t('common.save')"
                      class="p-button-sm p-button-primary"
                      @click="desarXmlVersion(version)"
                    />
                    <Button
                      icon="pi pi-trash"
                      :label="$t('common.delete')"
                      class="p-button-sm p-button-danger"
                      @click="eliminarXmlVersion(version)"
                    />
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- Últim professor -->
          <div class="field">
            <label for="ultim_professor">{{ $t('config.system.lastTeacher') }}</label>
            <Dropdown
              id="ultim_professor"
              v-model="settings.ultim_professor_subs"
              :options="ultimProfessorOptions"
              optionLabel="label"
              optionValue="value"
              :placeholder="$t('config.system.allTeachers')"
              :filter="true"
              class="w-full logo-field"
            />
            <small class="field-hint">
              {{ $t('config.system.lastTeacherHintLine1') }}
              {{ $t('config.system.lastTeacherHintLine2') }}
            </small>
          </div>

          <Divider />

          <!-- PDFs generats -->
          <div class="field">
            <div class="toolbar" style="margin-bottom: 0.5rem;">
              <label>{{ $t('config.system.generatedPdfs') }}</label>
              <Button
                icon="pi pi-refresh"
                @click="carregarPDFs"
                size="small"
                class="p-button-secondary"
                v-tooltip.top="$t('common.reload')"
              />
            </div>

            <div class="pdfs-list" v-if="pdfs.length > 0">
              <div v-for="pdf in pdfs" :key="pdf.filename" class="pdf-card">
                <div class="pdf-info">
                  <i class="pi pi-file-pdf" style="color: #ef4444; font-size: 1.2rem;"></i>
                  <span class="pdf-name">{{ pdf.filename }}</span>
                  <span class="pdf-size">{{ formatFileSize(pdf.size) }}</span>
                </div>
                <div class="pdf-actions">
                  <Button
                    icon="pi pi-download"
                    @click="descarregarPDF(pdf.filename)"
                    class="p-button-rounded p-button-text p-button-sm"
                    v-tooltip.top="$t('common.download')"
                  />
                  <Button
                    icon="pi pi-trash"
                    @click="eliminarPDF(pdf.filename)"
                    class="p-button-rounded p-button-text p-button-danger p-button-sm"
                    v-tooltip.top="$t('common.delete')"
                  />
                </div>
              </div>
            </div>
            <div v-else class="empty-message" style="margin-top: 0.5rem;">
              {{ $t('config.system.noPdfs') }}
            </div>
          </div>

          <div class="config-save-actions">
            <Tag v-if="teCanvis" severity="warning" :value="$t('common.unsavedChanges')" />
            <Button
              :label="$t('common.save')"
              icon="pi pi-save"
              @click="desar"
              class="p-button-success"
              :loading="desant"
              :disabled="!teCanvis"
            />
          </div>
        </div>
        </TabPanel>

      <!-- TAB 2: GRUPS I ABREVIATURES -->
        <TabPanel>
          <template #header>
            <span class="tab-header-lines">
              <span>{{ $t('config.tabs.groupsLine1') }}</span>
              <span>{{ $t('config.tabs.groupsLine2') }}</span>
            </span>
          </template>
          <div class="tab-content">
          <!-- Grups detectats -->
          <div class="field" style="margin-bottom: 1.5rem;">
            <div class="toolbar" style="margin-bottom: 0.5rem;">
              <label>{{ $t('config.groups.detectedLabel') }}</label>
              <Button
                icon="pi pi-refresh"
                :label="$t('config.groups.detectButton')"
                @click="detectarGrupsXML"
                class="p-button-secondary"
                size="small"
              />
            </div>

            <div v-if="grupsDetectats.length > 0" class="grups-detectats">
              <Tag
                v-for="(grup, idx) in grupsDetectats"
                :key="idx"
                :value="grup"
                severity="info"
              />
            </div>
            <div v-else class="empty-message" style="margin-top: 0.5rem;">
              {{ $t('config.groups.detectHint') }}
            </div>
          </div>

          <Divider />

          <!-- Abreviatures -->
          <div class="field">
            <div class="toolbar">
              <label>{{ $t('config.groups.abbrevLabel') }}</label>
              <Button
                :label="$t('config.groups.addAbbrev')"
                icon="pi pi-plus"
                @click="mostrarDialogAfegirAbreviatura = true"
                size="small"
                class="p-button-success"
              />
            </div>

            <div class="abreviatures-list">
              <div
                v-for="abr in abreviatures"
                :key="abr.id"
                class="abreviatura-card"
              >
                <div class="abreviatura-content">
                  <span class="grups-originals">{{ abr.grups_originals }}</span>
                  <i class="pi pi-arrow-right arrow-icon"></i>
                  <span class="abreviatura-text">{{ abr.abreviatura }}</span>
                </div>
                <div class="abreviatura-actions">
                  <Button
                    icon="pi pi-pencil"
                    @click="editarAbreviatura(abr)"
                    class="p-button-rounded p-button-text p-button-sm"
                    v-tooltip.top="$t('common.edit')"
                  />
                  <Button
                    icon="pi pi-trash"
                    @click="eliminarAbreviatura(abr.id)"
                    class="p-button-rounded p-button-text p-button-danger p-button-sm"
                    v-tooltip.top="$t('common.delete')"
                  />
                </div>
              </div>
              <div v-if="abreviatures.length === 0" class="empty-message">
                {{ $t('config.groups.noAbbrev') }}
              </div>
            </div>

            <p class="info-text">
              <i class="pi pi-info-circle"></i>
              {{ $t('config.groups.abbrevHint') }}
            </p>
          </div>
        </div>
        </TabPanel>

      <!-- TAB 3: PROFESSORS DE BAIXA -->
        <TabPanel>
          <template #header>
            <span class="tab-header-lines">
              <span>{{ $t('config.tabs.leaveLine1') }}</span>
              <span>{{ $t('config.tabs.leaveLine2') }}</span>
            </span>
          </template>
          <div class="tab-content">
          <div class="toolbar">
            <Tag severity="info" :value="$t('config.absences.count', { count: professorsBaixa.length })" />
            <Button
              :label="$t('common.add')"
              icon="pi pi-plus"
              @click="mostrarDialogProfessorBaixa = true"
              size="small"
              class="p-button-success"
            />
          </div>

          <div class="baixa-list">
            <div
              v-for="baixa in professorsBaixa"
              :key="baixa.id"
              class="baixa-card"
            >
              <div class="baixa-info">
                <span class="professor-nom">{{ baixa.professor }}</span>
                <span class="baixa-dates">{{ baixa.data_inici }} → {{ baixa.data_final }}</span>
                <span v-if="baixa.motiu" class="baixa-motiu">{{ baixa.motiu }}</span>
              </div>
              <div class="baixa-actions">
                <Button
                  icon="pi pi-pencil"
                  @click="editarProfessorBaixa(baixa)"
                  class="p-button-rounded p-button-text p-button-sm"
                  v-tooltip.top="$t('common.edit')"
                />
                <Button
                  icon="pi pi-trash"
                  @click="eliminarProfessorBaixa(baixa.id)"
                  class="p-button-rounded p-button-text p-button-danger p-button-sm"
                  v-tooltip.top="$t('common.delete')"
                />
              </div>
            </div>
            <div v-if="professorsBaixa.length === 0" class="empty-message">
              {{ $t('config.absences.none') }}
            </div>
          </div>

          <p class="info-text">
            <i class="pi pi-info-circle"></i>
            {{ $t('config.absences.hint') }}
          </p>
        </div>
        </TabPanel>

        <!-- TAB 4: PRIORITATS -->
        <TabPanel>
          <template #header>
            <span class="tab-header-lines">
              <span>{{ $t('config.tabs.prioritiesLine1') }}</span>
              <span>&nbsp;</span>
            </span>
          </template>
          <div class="tab-content" @click="handlePanelHeaderClick">
          <p class="info-text" style="margin-bottom: 1rem;">
            <i class="pi pi-info-circle"></i>
            {{ $t('config.priorities.introLine1') }}
            {{ $t('config.priorities.introLine2') }}
          </p>

          <!-- SECCIÓ 1: Ordre de Categories -->
          <Panel
            :header="$t('config.priorities.orderTitle')"
            :toggleable="true"
            v-model:collapsed="panelsPrioritatsCollapsed.ordre"
            @toggle="guardarEstatPanels"
          >
            <div class="toolbar" style="margin-bottom: 0.5rem;">
              <Button
                :label="$t('config.priorities.moveUp')"
                @click="moureCategoriaAmunt"
                size="small"
                :disabled="categoriaSeleccionadaIndex === null || categoriaSeleccionadaIndex === 0"
                v-tooltip.top="$t('config.priorities.moveUpHint')"
              />
              <Button
                :label="$t('config.priorities.moveDown')"
                @click="moureCategoriaAvall"
                size="small"
                :disabled="categoriaSeleccionadaIndex === null || categoriaSeleccionadaIndex >= ordreCategories.length - 1"
                v-tooltip.top="$t('config.priorities.moveDownHint')"
              />
              <Button
                :label="$t('config.priorities.addCategory')"
                @click="mostrarDialogAfegirCategoria = true"
                size="small"
                class="p-button-success"
              />
              <Button
                :label="$t('common.delete')"
                @click="eliminarCategoria"
                size="small"
                class="p-button-danger"
                :disabled="categoriaSeleccionadaIndex === null"
              />
            </div>

            <DataTable
              :value="ordreCategories"
              v-model:selection="categoriaSeleccionada"
              selectionMode="single"
              @row-select="onCategoriaSelect"
              @row-unselect="onCategoriaUnselect"
              :stripedRows="true"
              class="p-datatable-sm"
            >
              <Column field="ordre" :header="$t('config.priorities.order')" style="width: 80px;">
                <template #body="slotProps">
                  {{ slotProps.index + 1 }}
                </template>
              </Column>
              <Column field="activa" :header="$t('config.priorities.active')" style="width: 100px;">
                <template #body="slotProps">
                  <Checkbox
                    v-model="slotProps.data.activa"
                    :binary="true"
                  />
                </template>
              </Column>
              <Column field="categories" :header="$t('config.priorities.categories')">
                <template #body="slotProps">
                  {{ slotProps.data.categories.join(', ') }}
                </template>
              </Column>
            </DataTable>
          </Panel>

          <Divider />

          <!-- SECCIÓ 2: Pesos d'Aleatorietat per Categoria -->
          <Panel
            :header="$t('config.priorities.weightsTitle')"
            :toggleable="true"
            v-model:collapsed="panelsPrioritatsCollapsed.pesos"
            @toggle="guardarEstatPanels"
          >
            <p class="info-text" style="margin-bottom: 1rem;">
              <i class="pi pi-info-circle"></i>
              {{ $t('config.priorities.weightsHint') }}
            </p>

            <Accordion :multiple="true" :activeIndex="accordionActiveIndexes">
              <AccordionTab
                v-for="(cat, idx) in ordreCategories"
                :key="idx"
                :header="$t('config.priorities.categoryHeader', { index: idx + 1, items: cat.categories.join(', ') })"
              >
                <div class="categoria-pesos">
                  <div v-for="(assignatura, aIdx) in cat.categories" :key="aIdx" class="assignatura-row">
                    <div class="assignatura-header">
                      <label>{{ assignatura || $t('common.empty') }}</label>
                    </div>
                    <div class="assignatura-controls">
                      <InputNumber
                        v-model="pesos[assignatura]"
                        :min="1"
                        :max="10"
                        suffix=" pes"
                        showButtons
                        buttonLayout="horizontal"
                        :step="1"
                      />
                      <Button
                        icon="pi pi-trash"
                        class="p-button-rounded p-button-text p-button-danger p-button-sm"
                        @click="eliminarAssignaturaCategoria(assignatura, idx)"
                        v-tooltip.top="$t('config.priorities.deleteSubject')"
                      />
                    </div>
                    <small v-if="assignatura.toLowerCase() === 'alliberat'" class="field-hint">
                      {{ $t('config.priorities.freeHint') }}
                    </small>
                  </div>

                  <Button
                    :label="$t('config.priorities.addSubjectToCategory', { index: idx + 1 })"
                    @click="afegirAssignaturaCategoria(idx)"
                    size="small"
                    class="p-button-text"
                    style="margin-top: 0.5rem;"
                  />
                </div>
              </AccordionTab>
            </Accordion>
          </Panel>

          <Divider />

          <!-- SECCIÓ 3: Activitats No Substituibles -->
          <Panel
            :header="$t('config.priorities.noSubstTitle')"
            :toggleable="true"
            v-model:collapsed="panelsPrioritatsCollapsed.noSubst"
            @toggle="guardarEstatPanels"
          >
            <p class="info-text" style="margin-bottom: 1rem;">
              <i class="pi pi-info-circle"></i>
              {{ $t('config.priorities.noSubstHint') }}
            </p>

            <div class="toolbar" style="margin-bottom: 0.5rem;">
              <Tag severity="info" :value="$t('config.priorities.noSubstCount', { count: noSubstituir.length })" />
              <Button
                :label="$t('common.add')"
                icon="pi pi-plus"
                @click="mostrarDialogNoSubstituir = true"
                size="small"
                class="p-button-success"
              />
            </div>

            <div class="no-subst-list">
              <Tag
                v-for="(item, idx) in noSubstituir"
                :key="idx"
                :value="item || $t('common.empty')"
                severity="secondary"
              >
                <template #default>
                  {{ item || $t('common.empty') }}
                  <i class="pi pi-times" style="margin-left: 0.5rem; cursor: pointer;" @click="eliminarNoSubstituir(item)"></i>
                </template>
              </Tag>
            </div>
          </Panel>

          <Divider />

          <!-- SECCIÓ 4: Llista de Disponibles (PDF) -->
          <Panel
            :header="$t('config.priorities.availableListTitle')"
            :toggleable="true"
            v-model:collapsed="panelsPrioritatsCollapsed.disponibles"
            @toggle="guardarEstatPanels"
          >
            <p class="info-text" style="margin-bottom: 1rem;">
              <i class="pi pi-info-circle"></i>
              {{ $t('config.priorities.availableListHint') }}
            </p>

            <div style="display: flex; flex-direction: column; align-items: center; gap: 0.75rem; padding: 2rem 0;">
              <div style="display: flex; align-items: center; gap: 0.75rem;">
                <label style="font-size: 0.875rem; font-weight: 600; color: #374151; white-space: nowrap;">
                  {{ $t('config.priorities.startDate') }}
                </label>
                <input
                  type="date"
                  v-model="dataInicialPDF"
                  style="height: 36px; padding: 0 0.75rem; border: 1.5px solid #d1d5db; border-radius: 8px; font-size: 0.875rem; outline: none;"
                />
                <span style="font-size: 0.8rem; color: #9ca3af;">
                  {{ $t('config.priorities.startDateHint') }}
                </span>
              </div>
              <Button
                :label="$t('config.priorities.generateAllDaysPDF')"
                icon="pi pi-file-pdf"
                @click="generarPDFDisponiblesTotsDies"
                severity="danger"
                :loading="generantPDFDisponibles"
                size="large"
              />
            </div>
          </Panel>

          <!-- Botó desar -->
          <div style="display: flex; justify-content: center; margin-top: 1.5rem;">
            <Button
              :label="$t('config.priorities.saveAll')"
              @click="desarPrioitats"
              class="p-button-lg p-button-success"
              :loading="desantPrioritats"
              :disabled="!teCanvisPrioritats"
            />
          </div>
        </div>
        </TabPanel>

        <!-- TAB 5: CURSOS -->
        <TabPanel v-if="canManageUsers">
          <template #header>
            <span class="tab-header-lines">
              <span>{{ $t('config.tabs.coursesLine1') }}</span>
              <span>&nbsp;</span>
            </span>
          </template>
          <div class="tab-content">
            <div class="toolbar" style="margin-bottom: 0.75rem;">
              <label>{{ $t('config.courses.title') }}</label>
              <Button
                :label="$t('config.courses.new')"
                icon="pi pi-plus"
                size="small"
                @click="obrirNouCurs"
              />
            </div>

            <p class="camp-ajuda" style="margin-bottom: 0.75rem;">
              {{ $t('config.courses.help') }}
            </p>

            <DataTable :value="cursos" size="small" dataKey="id" :loading="carregantCursos">
              <template #empty>{{ $t('config.courses.empty') }}</template>

              <Column field="nom" :header="$t('config.courses.name')" />

              <Column :header="$t('config.courses.start')">
                <template #body="{ data }">{{ data.data_inici }}</template>
              </Column>

              <Column :header="$t('config.courses.end')">
                <template #body="{ data }">
                  <span v-if="data.data_fi">{{ data.data_fi }}</span>
                  <Tag v-else severity="success" :value="$t('config.courses.open')" />
                </template>
              </Column>

              <Column :header="$t('common.actions')" style="width: 110px;">
                <template #body="{ data }">
                  <Button
                    icon="pi pi-pencil"
                    class="p-button-text p-button-sm"
                    v-tooltip.top="$t('common.edit')"
                    @click="obrirEditarCurs(data)"
                  />
                  <Button
                    icon="pi pi-trash"
                    class="p-button-text p-button-sm p-button-danger"
                    v-tooltip.top="$t('common.delete')"
                    @click="eliminarCurs(data)"
                  />
                </template>
              </Column>
            </DataTable>
          </div>
        </TabPanel>

        <!-- TAB 6: USUARIS -->
        <TabPanel v-if="canManageUsers">
          <template #header>
            <span class="tab-header-lines">
              <span>{{ $t('config.tabs.usersLine1') }}</span>
              <span>&nbsp;</span>
            </span>
          </template>
          <div class="tab-content">
            <div class="toolbar" style="margin-bottom: 0.75rem;">
              <label>{{ $t('config.users.title') }}</label>
              <div class="user-tools">
                <Dropdown
                  v-if="props.currentRole === 'super_admin'"
                  v-model="userInstitutionFilter"
                  :options="userInstitutionOptions"
                  optionLabel="label"
                  optionValue="value"
                  :placeholder="$t('config.users.filterInstitution')"
                  class="p-inputtext-sm"
                />
                <Button
                  :icon="userSortAsc ? 'pi pi-sort-alpha-down' : 'pi pi-sort-alpha-up'"
                  class="p-button-sm p-button-text"
                  v-tooltip.top="$t('config.users.sort')"
                  @click="toggleUserSort"
                />
                <Button
                  icon="pi pi-plus"
                  class="p-button-sm"
                  :label="$t('config.users.add')"
                  iconPos="left"
                  @click="obrirNouUsuari"
                />
              </div>
            </div>

            <DataTable
              :value="usersFiltered"
              dataKey="id"
              :loading="usersLoading"
              class="p-datatable-sm"
            >
              <Column field="username" :header="$t('config.users.username')" />
              <Column field="role" :header="$t('config.users.role')" style="min-width: 7.5rem" />
              <Column v-if="props.currentRole === 'super_admin'" :header="$t('config.users.institucio')">
                <template #body="{ data }">
                  {{ data.institucio_display_name || data.institucio }}
                </template>
              </Column>
              <Column :header="$t('config.users.active')" bodyClass="text-center">
                <template #body="{ data }">
                  {{ data.active ? $t('config.users.activeYes') : $t('config.users.activeNo') }}
                </template>
              </Column>
              <Column :header="$t('common.actions')" bodyClass="text-center">
                <template #body="{ data }">
                  <div class="table-actions">
                    <Button
                      icon="pi pi-pencil"
                      class="p-button-text p-button-sm"
                      :disabled="data.role === 'super_admin'"
                      v-tooltip.top="data.role === 'super_admin' ? $t('config.users.superAdminLocked') : $t('common.edit')"
                      @click="editarUsuari(data)"
                    />
                    <Button
                      icon="pi pi-ban"
                      class="p-button-text p-button-sm p-button-danger"
                      :disabled="data.role === 'super_admin'"
                      v-tooltip.top="data.role === 'super_admin' ? $t('config.users.superAdminLocked') : $t('config.users.deactivateTitle')"
                      @click="desactivarUsuari(data)"
                    />
                    <Button
                      v-if="isSuperAdmin"
                      icon="pi pi-trash"
                      class="p-button-text p-button-sm p-button-danger"
                      :disabled="data.role === 'super_admin'"
                      v-tooltip.top="data.role === 'super_admin' ? $t('config.users.superAdminLocked') : $t('config.users.deleteTitle')"
                      @click="eliminarUsuari(data)"
                    />
                  </div>
                </template>
              </Column>
            </DataTable>
          </div>
        </TabPanel>

        <!-- TAB 6: INSTITUCIONS (SUPER ADMIN) -->
        <TabPanel v-if="isSuperAdmin">
          <template #header>
            <span class="tab-header-lines">
              <span>{{ $t('config.tabs.institutionsLine1') }}</span>
              <span>&nbsp;</span>
            </span>
          </template>
          <div class="tab-content">
            <div class="toolbar" style="margin-bottom: 0.75rem;">
              <label>{{ $t('config.institutions.title') }}</label>
              <Button
                icon="pi pi-plus"
                class="p-button-sm"
                :label="$t('config.institutions.add')"
                @click="obrirNovaInstitucio"
              />
            </div>

            <DataTable
              :value="institucions"
              dataKey="slug"
              class="p-datatable-sm"
            >
              <Column field="display_name" :header="$t('config.institutions.name')" />
              <Column field="slug" :header="$t('config.institutions.code')" style="width: 180px;" />
              <Column :header="$t('config.institutions.status')" bodyClass="text-center">
                <template #body="{ data }">
                  {{ data.active ? $t('config.institutions.active') : $t('config.institutions.inactive') }}
                </template>
              </Column>
              <Column :header="$t('common.actions')" bodyClass="text-center">
                <template #body="{ data }">
                  <div class="table-actions">
                    <Button
                      icon="pi pi-pencil"
                      class="p-button-text p-button-sm"
                      v-tooltip.top="$t('common.edit')"
                      @click="editarInstitucio(data)"
                    />
                    <Button
                      :icon="data.active ? 'pi pi-ban' : 'pi pi-check-circle'"
                      class="p-button-text p-button-sm"
                      v-tooltip.top="data.active ? $t('config.institutions.deactivate') : $t('config.institutions.activate')"
                      @click="confirmarCanviEstatInstitucio(data)"
                    />
                    <Button
                      icon="pi pi-trash"
                      class="p-button-text p-button-sm p-button-danger"
                      v-tooltip.top="$t('config.institutions.delete')"
                      @click="confirmarEliminarInstitucio(data)"
                    />
                  </div>
                </template>
              </Column>
            </DataTable>
          </div>
        </TabPanel>
      </TabView>
    </div>

    <!-- Diàleg afegir/editar abreviatura -->
    <Dialog
      v-model:visible="mostrarDialogAfegirAbreviatura"
      :header="abreviaturaEditant ? $t('config.groups.editAbbrevTitle') : $t('config.groups.addAbbrevTitle')"
      :modal="true"
      :style="{ width: '500px' }"
    >
      <div class="p-fluid">
        <div class="field">
          <label>{{ $t('config.groups.originalGroups') }}</label>
          <MultiSelect
            v-model="grupsSeleccionats"
            :options="grupsDetectats"
            :placeholder="$t('config.groups.selectGroups')"
            display="chip"
            :filter="true"
            class="w-full"
          />
          <small class="field-hint">
            {{ $t('config.groups.selectGroupsHint') }}
            <a @click="detectarGrupsXML" style="cursor: pointer; text-decoration: underline;">{{ $t('config.groups.detectInline') }}</a>
          </small>
        </div>

        <div class="field">
          <label>{{ $t('config.groups.abbrevLabel') }}</label>
          <InputText
            v-model="novaAbreviatura.abreviatura"
            :placeholder="$t('config.groups.abbrevPlaceholder')"
            @keyup.enter="desarAbreviatura"
          />
          <small class="field-hint">{{ $t('config.groups.abbrevHintShort') }}</small>
        </div>
      </div>

      <template #footer>
        <Button
          :label="$t('common.cancel')"
          @click="cancelarAbreviatura"
          class="p-button-text"
        />
        <Button
          :label="$t('common.save')"
          @click="desarAbreviatura"
          class="p-button-success"
          :disabled="grupsSeleccionats.length === 0 || !novaAbreviatura.abreviatura"
        />
      </template>
    </Dialog>

    <!-- Diàleg afegir/editar professor de baixa -->
    <Dialog
      v-model:visible="mostrarDialogProfessorBaixa"
      :header="professorBaixaEditant ? $t('config.absences.editTitle') : $t('config.absences.addTitle')"
      :modal="true"
      :style="{ width: '500px' }"
      :contentStyle="{ padding: '1rem 1.25rem' }"
    >
      <div class="p-fluid">
        <div class="field">
          <label>{{ $t('config.absences.teacher') }}</label>
          <Dropdown
            v-model="novaProfessorBaixa.professor"
            :options="professorsAll"
            :placeholder="$t('config.absences.selectTeacher')"
            :filter="true"
            :editable="true"
            class="w-full"
          />
        </div>

        <div class="field">
          <label>{{ $t('config.absences.startDate') }}</label>
          <Calendar
            v-model="novaProfessorBaixa.data_inici"
            dateFormat="yy-mm-dd"
            :showIcon="true"
            class="w-full"
          />
        </div>

        <div class="field">
          <label>{{ $t('config.absences.endDate') }}</label>
          <Calendar
            v-model="novaProfessorBaixa.data_final"
            dateFormat="yy-mm-dd"
            :showIcon="true"
            class="w-full"
          />
        </div>

        <div class="field">
          <label>{{ $t('config.absences.reasonOptional') }}</label>
          <InputText
            v-model="novaProfessorBaixa.motiu"
            :placeholder="$t('config.absences.reasonPlaceholder')"
          />
        </div>
      </div>

      <template #footer>
        <Button
          :label="$t('common.cancel')"
          @click="cancelarProfessorBaixa"
          class="p-button-text"
        />
        <Button
          :label="$t('common.save')"
          @click="desarProfessorBaixa"
          class="p-button-success"
          :disabled="!novaProfessorBaixa.professor || !novaProfessorBaixa.data_inici || !novaProfessorBaixa.data_final"
        />
      </template>
    </Dialog>

    <!-- Diàleg afegir no substituir -->
    <Dialog
      v-model:visible="mostrarDialogNoSubstituir"
      :header="$t('config.priorities.addNoSubstTitle')"
      :modal="true"
      :style="{ width: '500px' }"
    >
      <div class="p-fluid">
        <div class="field">
          <label>{{ $t('config.priorities.selectSubjectXml') }}</label>
          <Dropdown
            v-model="novaNoSubstituir"
            :options="assignaturesDisponibles"
            :placeholder="$t('config.priorities.selectSubjectPlaceholder')"
            :filter="true"
            :editable="true"
            class="w-full"
          />
          <small class="field-hint">
            {{ $t('config.priorities.customSubjectHint') }}
          </small>
        </div>
      </div>

      <template #footer>
        <Button
          :label="$t('common.cancel')"
          @click="cancelarNoSubstituir"
          class="p-button-text"
        />
        <Button
          :label="$t('common.save')"
          @click="desarNoSubstituir"
          class="p-button-success"
          :disabled="!novaNoSubstituir"
        />
      </template>
    </Dialog>

    <!-- Diàleg afegir categoria -->
    <Dialog
      v-model:visible="mostrarDialogAfegirCategoria"
      :header="$t('config.priorities.addCategoryTitle')"
      :modal="true"
      :style="{ width: '500px' }"
    >
      <div class="p-fluid">
        <div class="field">
          <label>{{ $t('config.priorities.subjectsComma') }}</label>
          <InputText
            v-model="novaCategoria"
            :placeholder="$t('config.priorities.categoryPlaceholder')"
            @keyup.enter="afegirCategoriaDialog"
          />
          <small class="field-hint">{{ $t('config.priorities.subjectsCommaHint') }}</small>
        </div>
      </div>

      <template #footer>
        <Button
          :label="$t('common.cancel')"
          @click="mostrarDialogAfegirCategoria = false; novaCategoria = ''"
          class="p-button-text"
        />
        <Button
          :label="$t('common.add')"
          @click="afegirCategoriaDialog"
          class="p-button-success"
          :disabled="!novaCategoria.trim()"
        />
      </template>
    </Dialog>

    <!-- Diàleg afegir assignatura a categoria -->
    <Dialog
      v-model:visible="mostrarDialogAfegirAssignatura"
      :header="$t('config.priorities.addSubjectTitle', { index: categoriaAfegirAssignaturaIdx !== null ? categoriaAfegirAssignaturaIdx + 1 : '' })"
      :modal="true"
      :style="{ width: '500px' }"
    >
      <div class="p-fluid">
        <div class="field">
          <label>{{ $t('config.priorities.selectSubjectXml') }}</label>
          <Dropdown
            v-model="assignaturaSeleccionada"
            :options="assignaturesDisponibles"
            :placeholder="$t('config.priorities.selectSubjectPlaceholder')"
            :filter="true"
            :editable="true"
            class="w-full"
          />
          <small class="field-hint">
            {{ $t('config.priorities.customSubjectHint') }}
          </small>
        </div>
      </div>

      <template #footer>
        <Button
          :label="$t('common.cancel')"
          @click="mostrarDialogAfegirAssignatura = false; assignaturaSeleccionada = null"
          class="p-button-text"
        />
        <Button
          :label="$t('common.add')"
          @click="desarAssignaturaCategoria"
          class="p-button-success"
          :disabled="!assignaturaSeleccionada"
        />
      </template>
    </Dialog>

    <!-- Diàleg crear/editar usuari -->
    <Dialog
      v-model:visible="mostrarDialogUsuari"
      :modal="true"
      :style="{ width: '480px' }"
      :contentStyle="{ padding: '1rem 1.25rem' }"
      class="user-dialog"
      :key="userDialogKey"
    >
      <template #header>
        <span class="dialog-header">
          <i
            :class="usuariEditant ? 'pi pi-user-edit' : 'pi pi-user-plus'"
            aria-hidden="true"
          ></i>
          <span>{{ usuariEditant ? $t('config.users.editTitle') : $t('config.users.addTitle') }}</span>
        </span>
      </template>
      <div class="p-fluid">
        <div class="field">
          <label>{{ $t('config.users.username') }}</label>
          <InputText v-model="usuariForm.username" autocomplete="new-username" name="new-username" />
        </div>
        <div class="field">
          <label>{{ $t('config.users.password') }}</label>
          <Password
            v-model="usuariForm.password"
            :feedback="false"
            toggleMask
            :placeholder="usuariEditant ? $t('config.users.passwordOptional') : ''"
            class="w-full password-with-eye"
            :inputProps="{ autocomplete: 'new-password', name: 'new-password' }"
          />
        </div>
        <div class="field">
          <label>{{ $t('config.users.role') }}</label>
          <Dropdown
            v-model="usuariForm.role"
            :options="roleOptions"
            optionLabel="label"
            optionValue="value"
            class="w-full user-role-dropdown"
          />
        </div>
        <div v-if="props.currentRole === 'super_admin'" class="field">
          <label>{{ $t('config.users.institucio') }}</label>
          <Dropdown
            v-model="usuariForm.institucio"
            :options="institucionsOptions"
            class="w-full"
          />
        </div>
        <div class="field checkbox-field">
          <Checkbox v-model="usuariForm.active" binary />
          <span>{{ $t('config.users.active') }}</span>
        </div>
      </div>

      <template #footer>
        <Button :label="$t('common.cancel')" class="p-button-text" @click="tancarDialogUsuari" />
        <Button
          :label="$t('common.save')"
          class="p-button-success"
          :disabled="!usuariForm.username || (!usuariEditant && !usuariForm.password)"
          @click="desarUsuari"
        />
      </template>
    </Dialog>

    <!-- Diàleg crear/editar institució -->
    <Dialog
      v-model:visible="mostrarDialogInstitucio"
      :modal="true"
      :style="{ width: '480px' }"
      :contentStyle="{ padding: '1rem 1.25rem' }"
    >
      <template #header>
        <span class="dialog-header">
          <i
            :class="institucioEditant ? 'pi pi-pencil' : 'pi pi-plus'"
            aria-hidden="true"
          ></i>
          <span>{{ institucioEditant ? $t('config.institutions.editTitle') : $t('config.institutions.addTitle') }}</span>
        </span>
      </template>
      <div class="p-fluid">
        <div class="field">
          <label>{{ $t('config.institutions.code') }}</label>
          <InputText
            v-model="institucioForm.slug"
            :placeholder="$t('config.institutions.codePlaceholder')"
            :disabled="!!institucioEditant"
          />
        </div>
        <div class="field">
          <label>{{ $t('config.institutions.name') }}</label>
          <InputText
            v-model="institucioForm.display_name"
            :placeholder="$t('config.institutions.namePlaceholder')"
          />
        </div>
      </div>

      <template #footer>
        <Button :label="$t('common.cancel')" class="p-button-text" @click="tancarDialogInstitucio" />
        <Button
          :label="$t('common.save')"
          class="p-button-success"
          :disabled="!institucioForm.slug || !institucioForm.display_name"
          @click="desarInstitucio"
        />
      </template>
    </Dialog>

    <!-- Diàleg confirmació forta institució -->
    <Dialog
      v-model:visible="mostrarConfirmInstitucio"
      :modal="true"
      :style="{ width: '520px' }"
      :contentStyle="{ padding: '1rem 1.25rem' }"
    >
      <template #header>
        <span class="dialog-header">
          <i class="pi pi-exclamation-triangle" aria-hidden="true"></i>
          <span>{{ confirmInstitucioTitle }}</span>
        </span>
      </template>
      <div class="p-fluid">
        <p class="field-hint">{{ confirmInstitucioMessage }}</p>
        <div class="field">
          <label>{{ $t('config.institutions.confirmLabel') }}</label>
          <InputText v-model="confirmInstitucioInput" />
        </div>
      </div>

      <template #footer>
        <Button :label="$t('common.cancel')" class="p-button-text" @click="tancarConfirmInstitucio" />
        <Button
          :label="confirmInstitucioActionLabel"
          class="p-button-danger"
          :disabled="!confirmInstitucioInput"
          @click="executarAccioInstitucio"
        />
      </template>
    </Dialog>

    <!-- Diàleg: nou / editar curs -->
    <Dialog
      v-model:visible="mostrarDialegCurs"
      :modal="true"
      :style="{ width: '460px' }"
      :contentStyle="{ padding: '1rem 1.25rem' }"
    >
      <template #header>
        <span class="dialog-header">
          <i class="pi pi-calendar" aria-hidden="true"></i>
          <span>{{ cursForm.id ? $t('config.courses.editTitle') : $t('config.courses.newTitle') }}</span>
        </span>
      </template>

      <div class="p-fluid">
        <div class="field">
          <label>{{ $t('config.courses.name') }}</label>
          <InputText v-model="cursForm.nom" :placeholder="$t('config.courses.namePlaceholder')" />
        </div>
        <div class="field">
          <label>{{ $t('config.courses.start') }}</label>
          <Calendar v-model="cursForm.data_inici" dateFormat="dd/mm/yy" :showIcon="true" />
          <small class="field-hint">{{ $t('config.courses.startHint') }}</small>
        </div>
      </div>

      <template #footer>
        <Button :label="$t('common.cancel')" class="p-button-text" @click="mostrarDialegCurs = false" />
        <Button
          :label="$t('common.save')"
          icon="pi pi-check"
          :disabled="!cursForm.nom || !cursForm.data_inici"
          :loading="desantCurs"
          @click="desarCurs"
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
import { ref, watch, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import axios from 'axios'
import { useToast } from 'primevue/usetoast'
import { useConfirm } from 'primevue/useconfirm'
import Dialog from 'primevue/dialog'
import Dropdown from 'primevue/dropdown'
import MultiSelect from 'primevue/multiselect'
import InputText from 'primevue/inputtext'
import InputNumber from 'primevue/inputnumber'
import Calendar from 'primevue/calendar'
import Button from 'primevue/button'
import Password from 'primevue/password'
import Divider from 'primevue/divider'
import Tag from 'primevue/tag'
import TabView from 'primevue/tabview'
import TabPanel from 'primevue/tabpanel'
import Panel from 'primevue/panel'
import Accordion from 'primevue/accordion'
import AccordionTab from 'primevue/accordiontab'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Checkbox from 'primevue/checkbox'
import { setLocale } from '../i18n'

const toast = useToast()
const { t, locale } = useI18n()
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
  }
})

const emit = defineEmits(['update:visible', 'cursos-canviats'])

const loading = ref(false)
const xmlMissingNotified = ref(false)
const xmlVersionsLoading = ref(false)
const xmlVersions = ref([])
const desant = ref(false)
const settingsOriginal = ref(null)
const settings = ref({
  institucio: null,
  idioma: 'ca',
  xml_horari_path: '',
  export_dir: 'exports',
  ultim_professor_subs: '',
  institucio_display_name: '',
  data_dir: '',
  no_substituir: [],
  logo_path: ''
})

const institucions = ref([])
const idiomes = ref([])
const professors = ref([])
const users = ref([])
const userInstitutionFilter = ref('')
const userSortAsc = ref(true)
const usersLoading = ref(false)
const mostrarDialogUsuari = ref(false)
const usuariEditant = ref(null)
const userDialogKey = ref(0)
const usuariForm = ref({
  id: null,
  username: '',
  password: '',
  role: 'user',
  institucio: '',
  active: true
})
const mostrarDialogInstitucio = ref(false)
const institucioEditant = ref(null)
const institucioForm = ref({
  slug: '',
  display_name: ''
})
const mostrarConfirmInstitucio = ref(false)
const confirmInstitucioInput = ref('')
const confirmInstitucioAction = ref('')
const confirmInstitucioTarget = ref(null)

const canManageUsers = computed(() => ['admin', 'super_admin'].includes(props.currentRole || ''))
const isSuperAdmin = computed(() => props.currentRole === 'super_admin')
const institucionsOptions = computed(() => (
  institucions.value
    .filter((inst) => inst.active !== false)
    .map((inst) => ({
      label: inst.display_name || inst.slug,
      value: inst.slug
    }))
))
const userInstitutionOptions = computed(() => ([
  { label: t('common.all'), value: '' },
  ...institucionsOptions.value
]))
const confirmInstitucioRequired = computed(() => {
  if (!confirmInstitucioTarget.value) return ''
  return confirmInstitucioAction.value === 'delete'
    ? `ELIMINA ${confirmInstitucioTarget.value.slug}`
    : confirmInstitucioTarget.value.slug
})
const confirmInstitucioTitle = computed(() => {
  if (confirmInstitucioAction.value === 'delete') return t('config.institutions.deleteTitle')
  if (confirmInstitucioAction.value === 'deactivate') return t('config.institutions.deactivateTitle')
  if (confirmInstitucioAction.value === 'activate') return t('config.institutions.activateTitle')
  return t('common.confirm')
})
const confirmInstitucioMessage = computed(() => {
  if (!confirmInstitucioTarget.value) return ''
  return confirmInstitucioAction.value === 'delete'
    ? t('config.institutions.deleteMessage', { slug: confirmInstitucioTarget.value.slug, confirm: confirmInstitucioRequired.value })
    : t('config.institutions.deactivateMessage', { slug: confirmInstitucioTarget.value.slug, confirm: confirmInstitucioRequired.value })
})
const confirmInstitucioActionLabel = computed(() => {
  if (confirmInstitucioAction.value === 'delete') return t('config.institutions.delete')
  if (confirmInstitucioAction.value === 'deactivate') return t('config.institutions.deactivate')
  if (confirmInstitucioAction.value === 'activate') return t('config.institutions.activate')
  return t('common.confirm')
})
const usersFiltered = computed(() => {
  const baseList = users.value
  const filteredList = (props.currentRole === 'super_admin' && userInstitutionFilter.value)
    ? baseList.filter((user) => user.institucio === userInstitutionFilter.value)
    : baseList
  return filteredList.sort((a, b) => {
  const cmp = (a.username || '').localeCompare(
    b.username || '',
    locale.value || 'ca',
    { sensitivity: 'base' }
  )
    return userSortAsc.value ? cmp : -cmp
  })
})
const roleOptions = computed(() => {
  if (props.currentRole === 'super_admin') {
    return [
      { label: 'super_admin', value: 'super_admin' },
      { label: 'admin', value: 'admin' },
      { label: 'user', value: 'user' }
    ]
  }
  return [
    { label: 'admin', value: 'admin' },
    { label: 'user', value: 'user' }
  ]
})


// Abreviatures
const abreviatures = ref([])
const mostrarDialogAfegirAbreviatura = ref(false)
const abreviaturaEditant = ref(null)
const novaAbreviatura = ref({
  grups_originals: '',
  abreviatura: ''
})

// Professors (TOTS, sense límit)
const professorsAll = ref([])
const ultimProfessorOptions = computed(() => ([
  { label: t('common.all'), value: '' },
  ...professorsAll.value.map((prof) => ({ label: prof, value: prof }))
]))

// Professors de baixa
const professorsBaixa = ref([])
const mostrarDialogProfessorBaixa = ref(false)
const professorBaixaEditant = ref(null)
const novaProfessorBaixa = ref({
  professor: '',
  data_inici: null,
  data_final: null,
  motiu: ''
})

// No substituir
const noSubstituir = ref([])
const mostrarDialogNoSubstituir = ref(false)
const novaNoSubstituir = ref('')

// PDFs
const pdfs = ref([])

const logoUrl = ref('')
let logoObjectUrl = ''
const logoNom = ref('')

// Grups detectats de l'XML
const grupsDetectats = ref([])
const grupsSeleccionats = ref([])

// Prioritats
const ordreCategories = ref([])  // Array de {categories: ["Reforç", "alliberat"], activa: true}
const pesos = ref({})  // {assignatura: pes}
const prioritiesSnapshot = ref('')
const categoriaSeleccionada = ref(null)
const categoriaSeleccionadaIndex = ref(null)
const accordionActiveIndexes = ref([])  // Índexos dels accordions oberts
const mostrarDialogAfegirCategoria = ref(false)
const novaCategoria = ref('')
const desantPrioritats = ref(false)

// Diàleg afegir assignatura a categoria
const mostrarDialogAfegirAssignatura = ref(false)
const categoriaAfegirAssignaturaIdx = ref(null)
const assignaturesDisponibles = ref([])
const assignaturaSeleccionada = ref(null)

// Llista de disponibles (PDF)
const generantPDFDisponibles = ref(false)
const dataInicialPDF = ref('')

// Estat collapsed dels Panels de prioritats (guardat a localStorage)
const panelsPrioritatsCollapsed = ref({
  ordre: false,
  pesos: false,
  noSubst: false,
  disponibles: true
})

// Carregar estat dels panels des de localStorage
const carregarEstatPanels = () => {
  try {
    const saved = localStorage.getItem('prioritats_panels_collapsed')
    if (saved) {
      panelsPrioritatsCollapsed.value = JSON.parse(saved)
    }
  } catch (e) {
    console.error('Error carregant estat panels:', e)
  }
}

// Guardar estat dels panels a localStorage
const guardarEstatPanels = () => {
  try {
    localStorage.setItem('prioritats_panels_collapsed', JSON.stringify(panelsPrioritatsCollapsed.value))
  } catch (e) {
    console.error('Error guardant estat panels:', e)
  }
}

const getPrioritatsSnapshot = () => JSON.stringify({
  ordreCategories: ordreCategories.value,
  pesos: pesos.value
})

const teCanvisPrioritats = computed(() => {
  if (!prioritiesSnapshot.value) return false
  return getPrioritatsSnapshot() !== prioritiesSnapshot.value
})

const getSettingsSnapshot = () => JSON.stringify({
  institucio: settings.value.institucio || '',
  institucio_display_name: settings.value.institucio_display_name || '',
  idioma: settings.value.idioma || '',
  xml_horari_path: settings.value.xml_horari_path || '',
  export_dir: settings.value.export_dir || '',
  ultim_professor_subs: settings.value.ultim_professor_subs || '',
  logo_path: settings.value.logo_path || ''
})

const teCanvis = computed(() => {
  if (!settingsOriginal.value) return false
  return getSettingsSnapshot() !== settingsOriginal.value
})

const actualitzarSnapshot = () => {
  settingsOriginal.value = getSettingsSnapshot()
}

// Convertir string YYYY-MM-DD a Date object
const stringToDate = (dateStr) => {
  if (!dateStr) return null
  const [year, month, day] = dateStr.split('-')
  return new Date(parseInt(year), parseInt(month) - 1, parseInt(day))
}

const dateToString = (dateObj) => {
  if (!dateObj) return null
  const year = dateObj.getFullYear()
  const month = String(dateObj.getMonth() + 1).padStart(2, '0')
  const day = String(dateObj.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

const carregarSettings = async () => {
  loading.value = true
  try {
    const [
      settingsResp,
      idiomesResp,
      professorsResp,
      professorsAllResp,
      abreviaturesResp,
      professorsBaixaResp,
      noSubstituirResp,
      xmlVersionsResp
    ] = await Promise.all([
      axios.get('/api/settings'),
      axios.get('/api/settings/idiomes'),
      axios.get('/api/professors'),
      axios.get('/api/horari/professors/all'),
      axios.get('/api/config/abreviatures'),
      axios.get('/api/prioritats/professors-baixa'),
      axios.get('/api/prioritats/no-substituir'),
      axios.get('/api/settings/xml-versions')
    ])

    settings.value = settingsResp.data
    if (settingsResp.data?.xml_missing && !xmlMissingNotified.value) {
      toast.add({
        severity: 'warn',
        summary: t('common.warning'),
        detail: t('common.xmlMissing'),
        life: 4000
      })
      xmlMissingNotified.value = true
    }
    if (!settings.value.institucio_display_name) {
      settings.value.institucio_display_name = settings.value.institucio || ''
    }
    await carregarLogo()
    logoNom.value = settings.value.logo_path ? settings.value.logo_path.split('/').pop() : ''
    await carregarInstitucions()
    idiomes.value = idiomesResp.data.idiomes
    professors.value = professorsResp.data.professors
    professorsAll.value = professorsAllResp.data.professors
    abreviatures.value = abreviaturesResp.data.abreviatures
    professorsBaixa.value = professorsBaixaResp.data.professors_baixa
    noSubstituir.value = noSubstituirResp.data.assignatures
    xmlVersions.value = xmlVersionsResp.data.versions || []

    if (canManageUsers.value) {
      await carregarUsuaris()
      await carregarCursos()
      await carregarAvisosXml()
    }

    // Carregar prioritats
    await carregarPrioritats()
    actualitzarSnapshot()
  } catch (error) {
    console.error('Error carregant configuració:', error)
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: t('config.errors.loadConfig'),
      life: 3000
    })
  } finally {
    loading.value = false
  }
}

const carregarInstitucions = async () => {
  const resp = await axios.get('/api/settings/institucions')
  institucions.value = resp.data.institucions || []
}

const carregarXmlVersions = async () => {
  xmlVersionsLoading.value = true
  try {
    const resp = await axios.get('/api/settings/xml-versions')
    xmlVersions.value = resp.data.versions || []
  } catch (error) {
    console.error('Error carregant versions XML:', error)
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: t('config.errors.loadXmlVersions'),
      life: 3000
    })
  } finally {
    xmlVersionsLoading.value = false
  }
}

const carregarUsuaris = async () => {
  usersLoading.value = true
  try {
    const response = await axios.get('/api/users')
    users.value = response.data || []
  } catch (error) {
    console.error('Error carregant usuaris:', error)
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: t('config.users.loadError'),
      life: 3000
    })
  } finally {
    usersLoading.value = false
  }
}

const toggleUserSort = () => {
  userSortAsc.value = !userSortAsc.value
}

const carregarLogo = async () => {
  if (logoObjectUrl) {
    URL.revokeObjectURL(logoObjectUrl)
    logoObjectUrl = ''
  }

  try {
    const response = await axios.get('/api/files/logo', {
      responseType: 'blob',
      params: { ts: Date.now() },
      _silent: true,
    })
    logoObjectUrl = URL.createObjectURL(response.data)
    logoUrl.value = logoObjectUrl
  } catch (error) {
    if (error.response?.status !== 404) {
      console.error('Error carregant logo:', error)
    }
    logoUrl.value = ''
  }
}

const parseIsoDate = (value) => {
  if (!value) return null
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? null : date
}

const formatIsoDate = (dateObj) => {
  if (!dateObj) return null
  const year = dateObj.getFullYear()
  const month = String(dateObj.getMonth() + 1).padStart(2, '0')
  const day = String(dateObj.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

// ===== CURSOS =====
const cursos = ref([])
const carregantCursos = ref(false)
const desantCurs = ref(false)
const mostrarDialegCurs = ref(false)
// Un curs només té nom + data d'inici: la data de fi la deriva el sistema
// (= inici del curs següent − 1 dia; l'últim queda obert).
const cursForm = ref({ id: null, nom: '', data_inici: null })

// Data de vigència del pròxim XML que es pugi (null = avui)
const xmlVigentDesDe = ref(null)

// Cursos vigents/futurs que arrencarien amb l'horari d'un curs anterior
const avisosXml = ref([])

const carregarAvisosXml = async () => {
  try {
    const { data } = await axios.get('/api/cursos/validacio-xml')
    avisosXml.value = data
  } catch (error) {
    avisosXml.value = []
  }
}

// Si hi ha un curs que comença en el futur, oferir la seva data d'inici com a drecera:
// és el cas típic de "preparar l'horari del curs vinent".
const cursFuturSuggerit = computed(() => {
  const avui = formatIsoDate(new Date())
  return [...cursos.value]
    .filter(c => c.data_inici > avui)
    .sort((a, b) => a.data_inici.localeCompare(b.data_inici))[0] || null
})

const carregarCursos = async () => {
  carregantCursos.value = true
  try {
    const { data } = await axios.get('/api/cursos')
    cursos.value = data
  } catch (error) {
    toast.add({ severity: 'error', summary: t('common.error'), detail: t('config.courses.loadError'), life: 3000 })
  } finally {
    carregantCursos.value = false
  }
}

const obrirNouCurs = () => {
  cursForm.value = { id: null, nom: '', data_inici: null }
  mostrarDialegCurs.value = true
}

const obrirEditarCurs = (curs) => {
  cursForm.value = {
    id: curs.id,
    nom: curs.nom,
    data_inici: parseIsoDate(curs.data_inici)
  }
  mostrarDialegCurs.value = true
}

const desarCurs = async () => {
  desantCurs.value = true
  try {
    const payload = {
      nom: cursForm.value.nom,
      data_inici: formatIsoDate(cursForm.value.data_inici)
    }
    if (cursForm.value.id) {
      await axios.put(`/api/cursos/${cursForm.value.id}`, payload)
    } else {
      await axios.post('/api/cursos', payload)
    }
    mostrarDialegCurs.value = false
    await carregarCursos()
    await carregarAvisosXml()
    emit('cursos-canviats')
    toast.add({ severity: 'success', summary: t('common.saved'), life: 2000 })
  } catch (error) {
    const detail = error?.response?.data?.detail || t('config.courses.saveError')
    toast.add({ severity: 'error', summary: t('common.error'), detail, life: 4000 })
  } finally {
    desantCurs.value = false
  }
}

const eliminarCurs = (curs) => {
  confirm.require({
    message: t('config.courses.deleteConfirm', { nom: curs.nom }),
    header: t('common.confirmation'),
    icon: 'pi pi-exclamation-triangle',
    acceptClass: 'p-button-danger',
    accept: async () => {
      try {
        await axios.delete(`/api/cursos/${curs.id}`)
        await carregarCursos()
        await carregarAvisosXml()
        emit('cursos-canviats')
        toast.add({ severity: 'success', summary: t('common.deleted'), life: 2000 })
      } catch (error) {
        toast.add({ severity: 'error', summary: t('common.error'), life: 3000 })
      }
    }
  })
}

const xmlVersionsDisplay = computed(() => {
  const sorted = [...xmlVersions.value].sort((a, b) => (a.data_inici || '').localeCompare(b.data_inici || ''))
  return sorted.map((version, index) => {
    const next = sorted[index + 1]
    let dataFi = version.data_fi
    if (next?.data_inici) {
      const nextDate = parseIsoDate(next.data_inici)
      if (nextDate) {
        const prevDay = new Date(nextDate)
        prevDay.setDate(prevDay.getDate() - 1)
        dataFi = formatIsoDate(prevDay)
      }
    }
    version.data_fi = dataFi
    version._previousId = index > 0 ? sorted[index - 1].id : null
    return version
  })
})

const desarXmlVersion = async (version) => {
  try {
    await axios.put(`/api/settings/xml-versions/${version.id}`, {
      data_inici: version.data_inici || null,
      data_fi: version.data_fi || null
    })

    if (version._previousId) {
      const prevEnd = version.data_inici ? (() => {
        const d = parseIsoDate(version.data_inici)
        if (!d) return null
        d.setDate(d.getDate() - 1)
        return formatIsoDate(d)
      })() : null

      if (prevEnd) {
        await axios.put(`/api/settings/xml-versions/${version._previousId}`, {
          data_fi: prevEnd
        })
      }
    }
    toast.add({
      severity: 'success',
      summary: t('common.saved'),
      detail: t('config.system.xmlSaved'),
      life: 2500
    })
    await carregarXmlVersions()
  } catch (error) {
    console.error('Error desant versió XML:', error)
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: error.response?.data?.detail || t('config.errors.saveXmlVersion'),
      life: 3000
    })
  }
}

const eliminarXmlVersion = async (version) => {
  confirm.require({
    message: t('config.confirm.deleteXmlMessage', { path: version.path }),
    header: t('config.confirm.deleteXmlTitle'),
    icon: 'pi pi-exclamation-triangle',
    acceptLabel: t('common.delete'),
    rejectLabel: t('common.cancel'),
    acceptClass: 'p-button-danger',
    accept: async () => {
      try {
        await axios.delete(`/api/settings/xml-versions/${version.id}`)
        toast.add({
          severity: 'success',
          summary: t('common.deleted'),
          detail: t('config.system.xmlDeleted'),
          life: 2500
        })
        await carregarXmlVersions()
      } catch (error) {
        console.error('Error eliminant versió XML:', error)
        toast.add({
          severity: 'error',
          summary: t('common.error'),
          detail: error.response?.data?.detail || t('config.errors.deleteXmlVersion'),
          life: 3000
        })
      }
    }
  })
}

const resetUsuariForm = () => {
  const fallbackInstitucio = institucionsOptions.value[0]?.value || ''
  usuariForm.value = {
    id: null,
    username: '',
    password: '',
    role: 'user',
    institucio: props.currentInstitucio || fallbackInstitucio,
    active: true
  }
}

const obrirNouUsuari = () => {
  resetUsuariForm()
  usuariEditant.value = null
  userDialogKey.value += 1
  mostrarDialogUsuari.value = true
}

const editarUsuari = (user) => {
  if (user.role === 'super_admin') {
    toast.add({
      severity: 'warn',
      summary: t('common.warning'),
      detail: t('config.users.superAdminLocked'),
      life: 3000
    })
    return
  }
  usuariEditant.value = user
  usuariForm.value = {
    id: user.id,
    username: user.username,
    password: '',
    role: user.role,
    institucio: user.institucio,
    active: user.active
  }
  mostrarDialogUsuari.value = true
}

const tancarDialogUsuari = () => {
  mostrarDialogUsuari.value = false
  resetUsuariForm()
}

const obrirNovaInstitucio = () => {
  institucioEditant.value = null
  institucioForm.value = { slug: '', display_name: '' }
  mostrarDialogInstitucio.value = true
}

const editarInstitucio = (inst) => {
  institucioEditant.value = inst
  institucioForm.value = { slug: inst.slug, display_name: inst.display_name || '' }
  mostrarDialogInstitucio.value = true
}

const tancarDialogInstitucio = () => {
  mostrarDialogInstitucio.value = false
  institucioEditant.value = null
  institucioForm.value = { slug: '', display_name: '' }
}

const desarInstitucio = async () => {
  try {
    if (institucioEditant.value) {
      await axios.put(`/api/settings/institucions/${institucioForm.value.slug}`, {
        display_name: institucioForm.value.display_name
      })
    } else {
      await axios.post('/api/settings/institucions', {
        nom: institucioForm.value.slug,
        display_name: institucioForm.value.display_name
      })
    }
    toast.add({
      severity: 'success',
      summary: t('common.saved'),
      detail: t('config.institutions.saved'),
      life: 2500
    })
    tancarDialogInstitucio()
    await carregarInstitucions()
  } catch (error) {
    console.error('Error desant institució:', error)
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: error.response?.data?.detail || t('config.institutions.saveError'),
      life: 3000
    })
  }
}

const confirmarCanviEstatInstitucio = (inst) => {
  confirmInstitucioTarget.value = inst
  confirmInstitucioInput.value = ''
  confirmInstitucioAction.value = inst.active ? 'deactivate' : 'activate'
  mostrarConfirmInstitucio.value = true
}

const confirmarEliminarInstitucio = (inst) => {
  confirmInstitucioTarget.value = inst
  confirmInstitucioInput.value = ''
  confirmInstitucioAction.value = 'delete'
  mostrarConfirmInstitucio.value = true
}

const tancarConfirmInstitucio = () => {
  mostrarConfirmInstitucio.value = false
  confirmInstitucioInput.value = ''
  confirmInstitucioTarget.value = null
  confirmInstitucioAction.value = ''
}

const executarAccioInstitucio = async () => {
  if (!confirmInstitucioTarget.value) return
  if (confirmInstitucioInput.value !== confirmInstitucioRequired.value) {
    toast.add({
      severity: 'warn',
      summary: t('common.warning'),
      detail: t('config.institutions.confirmMismatch'),
      life: 2500
    })
    return
  }

  try {
    if (confirmInstitucioAction.value === 'delete') {
      await axios.delete(`/api/settings/institucions/${confirmInstitucioTarget.value.slug}`, {
        data: {
          mode: 'hard',
          confirm: confirmInstitucioInput.value
        }
      })
    } else {
      await axios.put(`/api/settings/institucions/${confirmInstitucioTarget.value.slug}/status`, {
        active: confirmInstitucioAction.value === 'activate'
      })
    }
    toast.add({
      severity: 'success',
      summary: t('common.saved'),
      detail: t('config.institutions.updated'),
      life: 2500
    })
    await carregarInstitucions()
  } catch (error) {
    console.error('Error actualitzant institució:', error)
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: error.response?.data?.detail || t('config.institutions.saveError'),
      life: 3000
    })
  } finally {
    tancarConfirmInstitucio()
  }
}
const desarUsuari = async () => {
  try {
    const institucioValue = typeof usuariForm.value.institucio === 'object'
      ? usuariForm.value.institucio?.value
      : usuariForm.value.institucio
    if (usuariEditant.value) {
      const payload = {
        username: usuariForm.value.username,
        role: usuariForm.value.role,
        active: usuariForm.value.active
      }
      if (props.currentRole === 'super_admin') {
        payload.institucio = institucioValue
      }
      if (usuariForm.value.password) {
        payload.password = usuariForm.value.password
      }
      await axios.put(`/api/users/${usuariForm.value.id}`, payload)
    } else {
      const payload = {
        username: usuariForm.value.username,
        password: usuariForm.value.password,
        role: usuariForm.value.role
      }
      if (props.currentRole === 'super_admin') {
        payload.institucio = institucioValue
      }
      await axios.post('/api/users', payload)
    }
    toast.add({
      severity: 'success',
      summary: t('common.saved'),
      detail: t('config.users.saved'),
      life: 2500
    })
    mostrarDialogUsuari.value = false
    await carregarUsuaris()
    resetUsuariForm()
  } catch (error) {
    console.error('Error desant usuari:', error)
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: error.response?.data?.detail || t('config.users.saveError'),
      life: 3000
    })
  }
}

const desactivarUsuari = (user) => {
  confirm.require({
    message: t('config.users.deactivateConfirm', { username: user.username }),
    header: t('config.users.deactivateTitle'),
    icon: 'pi pi-exclamation-triangle',
    acceptLabel: t('config.users.deactivateAction'),
    rejectLabel: t('common.cancel'),
    acceptClass: 'p-button-danger',
    accept: async () => {
      try {
        await axios.delete(`/api/users/${user.id}`)
        toast.add({
          severity: 'success',
          summary: t('common.deleted'),
          detail: t('config.users.deactivated'),
          life: 2500
        })
        await carregarUsuaris()
      } catch (error) {
        console.error('Error desactivant usuari:', error)
        toast.add({
          severity: 'error',
          summary: t('common.error'),
          detail: error.response?.data?.detail || t('config.users.deleteError'),
          life: 3000
        })
      }
    }
  })
}

const eliminarUsuari = (user) => {
  confirm.require({
    message: t('config.users.deleteConfirm', { username: user.username }),
    header: t('config.users.deleteTitle'),
    icon: 'pi pi-exclamation-triangle',
    acceptLabel: t('common.delete'),
    rejectLabel: t('common.cancel'),
    acceptClass: 'p-button-danger',
    accept: async () => {
      try {
        await axios.delete(`/api/users/${user.id}/hard`)
        toast.add({
          severity: 'success',
          summary: t('common.deleted'),
          detail: t('config.users.deleted'),
          life: 2500
        })
        await carregarUsuaris()
      } catch (error) {
        console.error('Error eliminant usuari:', error)
        toast.add({
          severity: 'error',
          summary: t('common.error'),
          detail: error.response?.data?.detail || t('config.users.deleteError'),
          life: 3000
        })
      }
    }
  })
}

const pujarLogo = async (event) => {
  const file = event.target.files[0]
  if (!file) return

  const formData = new FormData()
  formData.append('file', file)

  try {
    const response = await axios.post('/api/files/upload-logo', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    settings.value.logo_path = response.data.path
    logoNom.value = response.data.filename
    await carregarLogo()
    actualitzarSnapshot()
    toast.add({
      severity: 'success',
      summary: t('config.system.logoUploaded'),
      detail: response.data.message,
      life: 3000
    })
  } catch (error) {
    console.error('Error pujant logo:', error)
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: error.response?.data?.detail || t('config.errors.uploadLogo'),
      life: 3000
    })
  } finally {
    event.target.value = ''
  }
}

// ===== FUNCIONS PRIORITATS =====

const onCategoriaSelect = (event) => {
  categoriaSeleccionadaIndex.value = ordreCategories.value.indexOf(event.data)
}

const onCategoriaUnselect = () => {
  categoriaSeleccionadaIndex.value = null
}

const moureCategoriaAmunt = () => {
  if (categoriaSeleccionadaIndex.value === null || categoriaSeleccionadaIndex.value === 0) return

  const idx = categoriaSeleccionadaIndex.value
  const temp = ordreCategories.value[idx]
  ordreCategories.value[idx] = ordreCategories.value[idx - 1]
  ordreCategories.value[idx - 1] = temp

  categoriaSeleccionadaIndex.value = idx - 1
  categoriaSeleccionada.value = ordreCategories.value[idx - 1]
}

const moureCategoriaAvall = () => {
  if (categoriaSeleccionadaIndex.value === null || categoriaSeleccionadaIndex.value >= ordreCategories.value.length - 1) return

  const idx = categoriaSeleccionadaIndex.value
  const temp = ordreCategories.value[idx]
  ordreCategories.value[idx] = ordreCategories.value[idx + 1]
  ordreCategories.value[idx + 1] = temp

  categoriaSeleccionadaIndex.value = idx + 1
  categoriaSeleccionada.value = ordreCategories.value[idx + 1]
}

const afegirCategoriaDialog = () => {
  if (!novaCategoria.value.trim()) return

  // Dividir per comes i netejar
  const categories = novaCategoria.value.split(',').map(c => c.trim()).filter(c => c)

  if (categories.length === 0) return

  ordreCategories.value.push({ categories, activa: true })  // Per defecte activa

  // Inicialitzar pesos a 1 per a cada assignatura nova
  categories.forEach(cat => {
    if (!pesos.value[cat]) {
      pesos.value[cat] = 1
    }
  })

  toast.add({
    severity: 'success',
    summary: t('common.added'),
    detail: t('config.priorities.categoryAdded', { count: categories.length }),
    life: 3000
  })

  mostrarDialogAfegirCategoria.value = false
  novaCategoria.value = ''
}

const eliminarCategoria = () => {
  if (categoriaSeleccionadaIndex.value === null) return

  const categoria = ordreCategories.value[categoriaSeleccionadaIndex.value]

  // Confirmar
  if (!confirm(t('config.priorities.deleteCategoryConfirm', {
    index: categoriaSeleccionadaIndex.value + 1,
    count: categoria.categories.length
  }))) {
    return
  }

  ordreCategories.value.splice(categoriaSeleccionadaIndex.value, 1)
  categoriaSeleccionada.value = null
  categoriaSeleccionadaIndex.value = null

  toast.add({
    severity: 'success',
    summary: t('common.deleted'),
    detail: t('config.priorities.categoryDeleted'),
    life: 3000
  })
}

const afegirAssignaturaCategoria = async (categoriaIdx) => {
  // Obrir diàleg
  categoriaAfegirAssignaturaIdx.value = categoriaIdx
  assignaturaSeleccionada.value = null
  mostrarDialogAfegirAssignatura.value = true
}

const desarAssignaturaCategoria = () => {
  if (!assignaturaSeleccionada.value) return

  const categoriaIdx = categoriaAfegirAssignaturaIdx.value
  const assignatura = assignaturaSeleccionada.value

  // Comprovar si ja existeix
  if (ordreCategories.value[categoriaIdx].categories.includes(assignatura)) {
    toast.add({
      severity: 'warn',
      summary: t('common.duplicate'),
      detail: t('config.priorities.subjectDuplicate', { subject: assignatura, index: categoriaIdx + 1 }),
      life: 3000
    })
    return
  }

  // Afegir a la categoria
  ordreCategories.value[categoriaIdx].categories.push(assignatura)

  // Inicialitzar pes si no existeix
  if (!pesos.value[assignatura]) {
    pesos.value[assignatura] = 1
  }

  toast.add({
    severity: 'success',
    summary: t('common.added'),
    detail: t('config.priorities.subjectAdded', { subject: assignatura, index: categoriaIdx + 1 }),
    life: 3000
  })

  // Tancar diàleg
  mostrarDialogAfegirAssignatura.value = false
  assignaturaSeleccionada.value = null
}

const eliminarAssignaturaCategoria = (assignatura, categoriaIdx) => {
  if (!confirm(t('config.priorities.deleteSubjectConfirm', { subject: assignatura, index: categoriaIdx + 1 }))) return

  const idx = ordreCategories.value[categoriaIdx].categories.indexOf(assignatura)
  if (idx !== -1) {
    ordreCategories.value[categoriaIdx].categories.splice(idx, 1)

    toast.add({
      severity: 'success',
      summary: t('common.deleted'),
      detail: t('config.priorities.subjectDeleted', { subject: assignatura }),
      life: 3000
    })
  }
}

const carregarAssignaturesXML = async () => {
  try {
    const response = await axios.get('/api/horari/assignatures/detectar')
    assignaturesDisponibles.value = response.data.assignatures
  } catch (error) {
    console.error('Error carregant assignatures XML:', error)
  }
}

const carregarPrioritats = async () => {
  try {
    const [assignaturesResp, categoriesResp] = await Promise.all([
      axios.get('/api/prioritats/assignatures'),
      axios.get('/api/prioritats/categories'),
      carregarAssignaturesXML()  // Carregar assignatures de l'XML
    ])

    // Crear mapa de categories per obtenir l'estat activa
    const categoriesMap = {}
    categoriesResp.data.categories.forEach(cat => {
      categoriesMap[cat.id] = {
        activa: cat.activa,
        ordre: cat.ordre
      }
    })

    // Agrupar assignatures per categoria_id
    const categoriesById = {}

    assignaturesResp.data.assignatures.forEach(assig => {
      if (!categoriesById[assig.categoria_id]) {
        categoriesById[assig.categoria_id] = {
          id: assig.categoria_id,
          assignatures: [],
          activa: categoriesMap[assig.categoria_id]?.activa || true
        }
      }

      categoriesById[assig.categoria_id].assignatures.push({
        nom: assig.assignatura,
        pes: assig.pes,
        ordre: assig.ordre,
        auto_assignada: assig.auto_assignada
      })

      // Guardar pes
      pesos.value[assig.assignatura] = assig.pes
    })

    // Convertir a ordreCategories: array de {categories: [...], activa: true/false}
    // Ordenar categories per ID (que correspon a l'ordre)
    ordreCategories.value = Object.keys(categoriesById)
      .sort((a, b) => parseInt(a) - parseInt(b))
      .map(catId => {
        const cat = categoriesById[catId]
        // Ordenar assignatures dins la categoria per ordre
        const assignaturesOrdenades = cat.assignatures
          .sort((a, b) => a.ordre - b.ordre)
          .map(a => a.nom)

        // Determinar si la categoria està activa: totes les assignatures tenen auto_assignada=true
        const activa = cat.assignatures.every(a => a.auto_assignada === true)

        return {
          categories: assignaturesOrdenades,
          activa: activa
        }
      })

    prioritiesSnapshot.value = getPrioritatsSnapshot()
  } catch (error) {
    console.error('Error carregant prioritats:', error)
  }
}

const desarPrioitats = async () => {
  desantPrioritats.value = true

  try {
    // Preparar dades per enviar
    const ordreCategoriesArray = ordreCategories.value.map(cat => cat.categories)
    const categoriesActives = ordreCategories.value.map(cat => cat.activa !== false)  // Default true si no està definit

    const response = await axios.put('/api/prioritats/desar-tot', {
      ordre_categories: ordreCategoriesArray,
      pesos: pesos.value,
      categories_actives: categoriesActives
    })

    toast.add({
      severity: 'success',
      summary: t('common.saved'),
      detail: response.data.message,
      life: 3000
    })

    // Recarregar prioritats per assegurar sincronització
    await carregarPrioritats()
  } catch (error) {
    console.error('Error desant prioritats:', error)
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: error.response?.data?.detail || t('config.errors.savePriorities'),
      life: 3000
    })
  } finally {
    desantPrioritats.value = false
  }
}

// Llista de disponibles - PDF de tots els dies
const generarPDFDisponiblesTotsDies = async () => {
  generantPDFDisponibles.value = true

  try {
    const response = await axios.post('/api/pdf/disponibles-tots-dies',
      { data_inici: dataInicialPDF.value || null },
      { responseType: 'blob' }
    )

    // Crear link de descàrrega
    const blob = new Blob([response.data], { type: 'application/pdf' })
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url

    const filename = response.headers['content-disposition']?.split('filename=')[1]?.replace(/"/g, '') ||
                     `disponibles_tots_dies_${new Date().toISOString().split('T')[0]}.pdf`

    link.download = filename
    link.click()
    window.URL.revokeObjectURL(url)

    toast.add({
      severity: 'success',
      summary: t('common.success'),
      detail: t('config.priorities.pdfGenerated'),
      life: 3000
    })
  } catch (error) {
    console.error('Error generant PDF:', error)
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: error.response?.data?.detail || t('config.errors.generatePDF'),
      life: 3000
    })
  } finally {
    generantPDFDisponibles.value = false
  }
}

// ===== FUNCIONS ALTRES =====

const desar = async () => {
  desant.value = true
  try {
    const response = await axios.put('/api/settings', {
      institucio: settings.value.institucio,
      ...(isSuperAdmin.value ? { institucio_display_name: settings.value.institucio_display_name } : {}),
      idioma: settings.value.idioma,
      xml_horari_path: settings.value.xml_horari_path,
      export_dir: settings.value.export_dir,
      ultim_professor_subs: settings.value.ultim_professor_subs || null
    })

    toast.add({
      severity: 'success',
      summary: t('common.saved'),
      detail: response.data.message,
      life: 3000
    })

    actualitzarSnapshot()
    setLocale(settings.value.idioma)
    // Mantindre obert: permet continuar configurant
  } catch (error) {
    console.error('Error desant configuració:', error)
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: error.response?.data?.detail || t('config.errors.saveConfig'),
      life: 3000
    })
  } finally {
    desant.value = false
  }
}

const handleVisibleChange = (newVal) => {
  if (newVal) {
    emit('update:visible', true)
    return
  }

  if (!teCanvis.value) {
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

// ===== FUNCIONS ABREVIATURES =====

const desarAbreviatura = async () => {
  // Convertir array de grups seleccionats a string separats per comes
  const grupsOriginalsString = grupsSeleccionats.value.join(',')

  if (!grupsOriginalsString || !novaAbreviatura.value.abreviatura) {
    return
  }

  try {
    if (abreviaturaEditant.value) {
      // Actualitzar existent
      await axios.put(`/api/config/abreviatures/${abreviaturaEditant.value}`, {
        grups_originals: grupsOriginalsString.trim(),
        abreviatura: novaAbreviatura.value.abreviatura.trim()
      })

      toast.add({
        severity: 'success',
        summary: t('common.updated'),
        detail: t('config.groups.abbrevUpdated'),
        life: 3000
      })
    } else {
      // Crear nova
      await axios.post('/api/config/abreviatures', {
        grups_originals: grupsOriginalsString.trim(),
        abreviatura: novaAbreviatura.value.abreviatura.trim()
      })

      toast.add({
        severity: 'success',
        summary: t('common.added'),
        detail: t('config.groups.abbrevAdded'),
        life: 3000
      })
    }

    // Recarregar abreviatures
    const response = await axios.get('/api/config/abreviatures')
    abreviatures.value = response.data.abreviatures

    // Tancar diàleg i netejar
    cancelarAbreviatura()
  } catch (error) {
    console.error('Error desant abreviatura:', error)
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: error.response?.data?.detail || t('config.errors.saveAbbrev'),
      life: 3000
    })
  }
}

const editarAbreviatura = (abr) => {
  abreviaturaEditant.value = abr.id
  novaAbreviatura.value = {
    grups_originals: abr.grups_originals,
    abreviatura: abr.abreviatura
  }

  // Convertir string separats per comes a array per al MultiSelect
  grupsSeleccionats.value = abr.grups_originals.split(',').map(g => g.trim())

  mostrarDialogAfegirAbreviatura.value = true
}

const eliminarAbreviatura = async (id) => {
  try {
    await axios.delete(`/api/config/abreviatures/${id}`)

    toast.add({
      severity: 'success',
      summary: t('common.deleted'),
      detail: t('config.groups.abbrevDeleted'),
      life: 3000
    })

    // Recarregar abreviatures
    const response = await axios.get('/api/config/abreviatures')
    abreviatures.value = response.data.abreviatures
  } catch (error) {
    console.error('Error eliminant abreviatura:', error)
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: error.response?.data?.detail || t('config.errors.deleteAbbrev'),
      life: 3000
    })
  }
}

const cancelarAbreviatura = () => {
  mostrarDialogAfegirAbreviatura.value = false
  abreviaturaEditant.value = null
  novaAbreviatura.value = {
    grups_originals: '',
    abreviatura: ''
  }
  grupsSeleccionats.value = []
}

// ===== FUNCIONS PROFESSORS DE BAIXA =====

const desarProfessorBaixa = async () => {
  if (!novaProfessorBaixa.value.professor || !novaProfessorBaixa.value.data_inici || !novaProfessorBaixa.value.data_final) {
    return
  }

  try {
    const baixaData = {
      professor: novaProfessorBaixa.value.professor,
      data_inici: dateToString(novaProfessorBaixa.value.data_inici),
      data_final: dateToString(novaProfessorBaixa.value.data_final),
      motiu: novaProfessorBaixa.value.motiu || ''
    }

    if (professorBaixaEditant.value) {
      // Actualitzar existent
      await axios.put(`/api/prioritats/professors-baixa/${professorBaixaEditant.value}`, baixaData)
      toast.add({
        severity: 'success',
        summary: t('common.updated'),
        detail: t('config.absences.updated'),
        life: 3000
      })
    } else {
      // Crear nou
      await axios.post('/api/prioritats/professors-baixa', baixaData)
      toast.add({
        severity: 'success',
        summary: t('common.added'),
        detail: t('config.absences.added'),
        life: 3000
      })
    }

    // Recarregar professors baixa
    const response = await axios.get('/api/prioritats/professors-baixa')
    professorsBaixa.value = response.data.professors_baixa

    // Tancar diàleg i netejar
    cancelarProfessorBaixa()
  } catch (error) {
    console.error('Error desant professor baixa:', error)
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: error.response?.data?.detail || t('config.errors.saveAbsence'),
      life: 3000
    })
  }
}

const editarProfessorBaixa = (baixa) => {
  professorBaixaEditant.value = baixa.id
  novaProfessorBaixa.value = {
    professor: baixa.professor,
    data_inici: stringToDate(baixa.data_inici),
    data_final: stringToDate(baixa.data_final),
    motiu: baixa.motiu || ''
  }
  mostrarDialogProfessorBaixa.value = true
}

const eliminarProfessorBaixa = async (id) => {
  try {
    await axios.delete(`/api/prioritats/professors-baixa/${id}`)

    toast.add({
      severity: 'success',
      summary: t('common.deleted'),
      detail: t('config.absences.deleted'),
      life: 3000
    })

    // Recarregar professors baixa
    const response = await axios.get('/api/prioritats/professors-baixa')
    professorsBaixa.value = response.data.professors_baixa
  } catch (error) {
    console.error('Error eliminant professor baixa:', error)
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: error.response?.data?.detail || t('config.errors.deleteAbsence'),
      life: 3000
    })
  }
}

const cancelarProfessorBaixa = () => {
  mostrarDialogProfessorBaixa.value = false
  professorBaixaEditant.value = null
  novaProfessorBaixa.value = {
    professor: '',
    data_inici: null,
    data_final: null,
    motiu: ''
  }
}

// ===== FUNCIONS NO SUBSTITUIR =====

const desarNoSubstituir = async () => {
  try {
    await axios.post('/api/prioritats/no-substituir', {
      assignatura: novaNoSubstituir.value
    })

    toast.add({
      severity: 'success',
      summary: t('common.added'),
      detail: t('config.priorities.noSubstAdded'),
      life: 3000
    })

    // Recarregar no substituir
    const response = await axios.get('/api/prioritats/no-substituir')
    noSubstituir.value = response.data.assignatures

    cancelarNoSubstituir()
  } catch (error) {
    console.error('Error desant no substituir:', error)
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: error.response?.data?.detail || t('config.errors.addNoSubst'),
      life: 3000
    })
  }
}

const eliminarNoSubstituir = async (assignatura) => {
  try {
    await axios.delete(`/api/prioritats/no-substituir/${encodeURIComponent(assignatura)}`)

    toast.add({
      severity: 'success',
      summary: t('common.deleted'),
      detail: t('config.priorities.noSubstDeleted'),
      life: 3000
    })

    // Recarregar no substituir
    const response = await axios.get('/api/prioritats/no-substituir')
    noSubstituir.value = response.data.assignatures
  } catch (error) {
    console.error('Error eliminant no substituir:', error)
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: error.response?.data?.detail || t('config.errors.deleteNoSubst'),
      life: 3000
    })
  }
}

const cancelarNoSubstituir = () => {
  mostrarDialogNoSubstituir.value = false
  novaNoSubstituir.value = ''
}

// ===== FUNCIONS ALTRES =====

const detectarGrupsXML = async () => {
  try {
    const response = await axios.get('/api/horari/grups/detectar')

    // Guardar grups detectats (usem grups_raw, els grups originals sense abreviar)
    grupsDetectats.value = response.data.grups_raw

    toast.add({
      severity: 'success',
      summary: t('common.detected'),
      detail: t('config.groups.detectedCount', { count: response.data.total_raw }),
      life: 3000
    })

    console.log('Grups detectats:', response.data)
  } catch (error) {
    console.error('Error detectant grups:', error)
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: error.response?.data?.detail || t('config.errors.detectGroups'),
      life: 3000
    })
  }
}

const pujarXML = async (event) => {
  const file = event.target.files[0]
  if (!file) return

  try {
    const formData = new FormData()
    formData.append('file', file)
    // Si no s'indica, el backend l'aplica des d'avui
    if (xmlVigentDesDe.value) {
      formData.append('data_inici', formatIsoDate(xmlVigentDesDe.value))
    }

    toast.add({
      severity: 'info',
      summary: t('common.uploading'),
      detail: t('config.system.uploadingFile', { name: file.name }),
      life: 2000
    })

    const response = await axios.post('/api/files/upload-xml', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    })

    // El path "actual" només canvia si la versió nova ja és vigent avui.
    // Si s'ha programat per a un curs futur, l'horari vigent segueix sent l'anterior.
    if (response.data.vigent_avui !== false) {
      settings.value.xml_horari_path = response.data.path
      actualitzarSnapshot()
    }

    toast.add({
      severity: 'success',
      summary: t('common.uploaded'),
      detail: response.data.vigent_avui === false
        ? t('config.system.xmlScheduled', { data: response.data.data_inici })
        : response.data.message,
      life: 4000
    })

    // Refrescar versions i avisos (pujar un XML pot resoldre una desincronització)
    await carregarXmlVersions()
    await carregarAvisosXml()
    xmlVigentDesDe.value = null
    event.target.value = ''
  } catch (error) {
    console.error('Error pujant XML:', error)
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: error.response?.data?.detail || t('config.errors.uploadXml'),
      life: 3000
    })
  }
}

// ===== FUNCIONS PDFs =====

const carregarPDFs = async () => {
  try {
    const response = await axios.get('/api/files/pdfs')
    pdfs.value = response.data.pdfs
  } catch (error) {
    console.error('Error carregant PDFs:', error)
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: t('config.errors.loadPdfs'),
      life: 3000
    })
  }
}

const descarregarPDF = async (filename) => {
  try {
    const response = await axios.get(
      `/api/files/pdfs/${encodeURIComponent(filename)}`,
      { responseType: 'blob' }
    )
    const contentType = response.headers['content-type'] || 'application/pdf'
    const blobUrl = window.URL.createObjectURL(new Blob([response.data], { type: contentType }))
    window.open(blobUrl, '_blank', 'noopener')
    setTimeout(() => window.URL.revokeObjectURL(blobUrl), 10000)

    toast.add({
      severity: 'success',
      summary: t('common.downloading'),
      detail: t('config.system.openingPdf', { name: filename }),
      life: 2000
    })
  } catch (error) {
    console.error('Error descarregant PDF:', error)
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: t('config.errors.downloadPdf'),
      life: 3000
    })
  }
}

const eliminarPDF = async (filename) => {
  try {
    await axios.delete(`/api/files/pdfs/${encodeURIComponent(filename)}`)

    toast.add({
      severity: 'success',
      summary: t('common.deleted'),
      detail: t('config.system.pdfDeleted', { name: filename }),
      life: 3000
    })

    // Recarregar llista
    await carregarPDFs()
  } catch (error) {
    console.error('Error eliminant PDF:', error)
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: t('config.errors.deletePdf'),
      life: 3000
    })
  }
}

const formatFileSize = (bytes) => {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i]
}

// Fer que tot el header dels panels sigui clicable
const handlePanelHeaderClick = (event) => {
  const header = event.target.closest('.p-panel-header')
  if (!header) return

  // Si ja s'ha clicat al botó toggle directament, no fer res
  if (event.target.closest('.p-panel-toggler')) return

  // Trobar el botó toggle i fer-hi clic
  const toggleBtn = header.querySelector('.p-panel-toggler')
  if (toggleBtn) {
    toggleBtn.click()
  }
}

// Carregar configuració quan s'obre el diàleg
watch(() => props.visible, (newVal) => {
  if (newVal) {
    if (props.currentRole !== 'super_admin') {
      userInstitutionFilter.value = ''
    }
    carregarEstatPanels()  // Carregar estat dels panels
    carregarSettings()
    carregarPDFs()
  }
})
</script>

<style scoped>
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

:deep(.p-dialog-content) {
  padding: 1rem 1rem 0.75rem !important;
}

.config-section {
  margin-bottom: 1rem;
}

.config-section h3 {
  font-size: 1.2rem;
  font-weight: 600;
  color: #2c3e50;
  margin-bottom: 1rem;
}

.field {
  margin-bottom: 1.5rem;
}

.field label {
  display: block;
  margin-bottom: 0.5rem;
  font-weight: 500;
  color: #374151;
  font-size: 0.95rem;
}

.loading-inline {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  color: #6b7280;
  font-size: 0.9rem;
}

.empty-inline {
  color: #6b7280;
  font-size: 0.9rem;
  padding: 0.5rem 0;
}

.xml-versions {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.xml-version-card {
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 0.75rem;
  background: #f9fafb;
}

.xml-version-row {
  display: flex;
  align-items: flex-end;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.xml-version-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
}

.xml-path {
  font-size: 0.85rem;
  color: #374151;
  word-break: break-all;
}

.xml-current {
  background: #dbeafe;
  color: #1d4ed8;
  font-size: 0.75rem;
  font-weight: 600;
  padding: 0.15rem 0.5rem;
  border-radius: 999px;
  white-space: nowrap;
}

.xml-version-dates {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}

.date-field {
  display: flex;
  align-items: baseline;
  gap: 0.4rem;
}

.date-inline-label {
  font-size: 0.75rem;
  color: #6b7280;
  white-space: nowrap;
  line-height: 1;
}

.xml-date {
  max-width: 150px;
}

/* Data de vigència del pròxim XML a pujar (preparar curs futur) */
.xml-vigencia {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
  margin-top: 0.5rem;
}

/* Avís: un curs arrencaria amb l'horari del curs anterior */
.xml-avis-desync {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  margin-top: 0.6rem;
  padding: 0.6rem 0.75rem;
  border: 1px solid #fcd34d;
  border-left: 4px solid #f59e0b;
  border-radius: 4px;
  background: #fffbeb;
  color: #78350f;
  font-size: 0.85rem;
}

.xml-avis-desync .pi {
  color: #d97706;
  font-size: 1.1rem;
}

.xml-avis-text {
  flex: 1;
  line-height: 1.35;
}

.xml-version-actions {
  display: flex;
  gap: 0.5rem;
  margin-left: auto;
  align-self: flex-end;
}

.table-actions {
  display: inline-flex;
  gap: 0.25rem;
  align-items: center;
  justify-content: center;
}

.checkbox-field {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.tab-header-lines {
  display: inline-flex;
  flex-direction: column;
  line-height: 1.1;
}

:deep(.password-with-eye) {
  width: 100%;
}

:deep(.password-with-eye .p-password),
:deep(.password-with-eye.p-icon-field) {
  position: relative;
  width: 100%;
}

:deep(.password-with-eye .p-password-input),
:deep(.password-with-eye.p-icon-field-right > .p-inputtext) {
  width: 100%;
  height: 2.25rem;
  line-height: 2.25rem;
  padding-right: 2.75rem;
}

:deep(.password-with-eye .p-input-icon),
:deep(.password-with-eye .p-password-show-icon),
:deep(.password-with-eye .p-password-hide-icon) {
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
  right: 0.75rem;
  line-height: 1;
  cursor: pointer;
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

.user-tools {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
}


@media (max-width: 720px) {
  .xml-version-row {
    gap: 0.5rem;
  }
  .xml-version-actions {
    width: 100%;
    justify-content: space-between;
  }
  .xml-version-dates {
    width: 100%;
    justify-content: space-between;
  }
  .date-field {
    flex-direction: column;
    align-items: flex-start;
    gap: 0.25rem;
  }
  .date-inline-label {
    line-height: 1.2;
  }
  .xml-date {
    max-width: 100%;
    width: 100%;
  }
}

.field-hint {
  display: block;
  margin-top: 0.35rem;
  color: #6b7280;
  font-size: 0.85rem;
  font-style: italic;
}

.no-subst-list {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  padding: 0.75rem;
  background: #f9fafb;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  min-height: 60px;
}

.no-subst-list:empty::before {
  content: 'Cap activitat configurada';
  color: #9ca3af;
  font-style: italic;
}

.w-full {
  width: 100%;
}

.user-role-dropdown {
  width: 100%;
}

.dialog-header {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  font-weight: 600;
}


/* Abreviatures */
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
  padding: 0.75rem;
  background: #f9fafb;
  border-radius: 6px;
}

.toolbar-left {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.abreviatures-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  max-height: 300px;
  overflow-y: auto;
  margin-bottom: 1rem;
}

.abreviatura-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.75rem 1rem;
  background: #f9fafb;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  transition: all 0.2s;
}

.abreviatura-card:hover {
  background: #f3f4f6;
  border-color: #d1d5db;
}

.abreviatura-content {
  display: flex;
  align-items: center;
  gap: 1rem;
  flex: 1;
}

.grups-originals {
  font-weight: 500;
  color: #374151;
  min-width: 150px;
}

.arrow-icon {
  color: #667eea;
  font-size: 0.9rem;
}

.abreviatura-text {
  color: #667eea;
  font-weight: 600;
  font-size: 1.05rem;
}

.abreviatura-actions {
  display: flex;
  gap: 0.25rem;
}

.empty-message {
  padding: 2rem;
  text-align: center;
  color: #9ca3af;
  font-style: italic;
  background: #f9fafb;
  border: 1px dashed #e5e7eb;
  border-radius: 6px;
}

.info-text {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem;
  background: #eff6ff;
  border: 1px solid #bfdbfe;
  border-radius: 6px;
  color: #1e40af;
  font-size: 0.9rem;
  margin-top: 1rem;
}

.info-text i {
  color: #3b82f6;
}

.config-save-actions {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 0.75rem;
  padding-top: 0.75rem;
  border-top: 1px solid #e5e7eb;
}

.logo-preview {
  margin-top: 0.75rem;
  display: flex;
  align-items: center;
}

.logo-preview img {
  max-height: 64px;
  max-width: 220px;
  border: 1px solid #e5e7eb;
  background: #ffffff;
  border-radius: 6px;
  padding: 0.25rem 0.5rem;
}

:deep(.logo-field.p-inputtext),
:deep(.logo-field.p-dropdown) {
  height: 2.4rem !important;
  min-height: 2.4rem !important;
  max-height: 2.4rem !important;
}

:deep(.logo-field.p-inputtext) {
  padding: 0.65rem 0.75rem !important;
}

:deep(.logo-field.p-dropdown .p-dropdown-label) {
  padding: 0.65rem 0.75rem !important;
  line-height: 1.4rem;
}

:deep(.uniform-inputgroup .p-inputtext),
:deep(.uniform-inputgroup .p-button) {
  height: 2.4rem !important;
}

:deep(.uniform-inputgroup .p-button) {
  padding: 0 !important;
  width: 2.4rem !important;
}

/* Tabs */
.tab-content {
  padding: 0.5rem 0;
  min-height: 400px;
}


.toolbar-right {
  display: flex;
  gap: 0.5rem;
}

/* Professors de baixa */
.baixa-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  margin: 1rem 0;
  max-height: 400px;
  overflow-y: auto;
}

.baixa-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.75rem 1rem;
  background: #f9fafb;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  transition: all 0.2s;
}

.baixa-card:hover {
  background: #f3f4f6;
  border-color: #d1d5db;
}

.baixa-info {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  flex: 1;
}

.professor-nom {
  font-weight: 600;
  color: #374151;
  font-size: 1.05rem;
}

.baixa-dates {
  color: #6b7280;
  font-size: 0.9rem;
}

.baixa-motiu {
  color: #9ca3af;
  font-size: 0.85rem;
  font-style: italic;
}

.baixa-actions {
  display: flex;
  gap: 0.25rem;
}

/* PDFs */
.pdfs-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  max-height: 300px;
  overflow-y: auto;
  margin-top: 0.5rem;
}

.pdf-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.75rem 1rem;
  background: #fff5f5;
  border: 1px solid #fecaca;
  border-radius: 6px;
  transition: all 0.2s;
}

.pdf-card:hover {
  background: #fef2f2;
  border-color: #fca5a5;
}

.pdf-info {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex: 1;
}

.pdf-name {
  font-weight: 500;
  color: #374151;
  flex: 1;
}

.pdf-size {
  color: #9ca3af;
  font-size: 0.85rem;
}

.pdf-actions {
  display: flex;
  gap: 0.25rem;
}

/* Prioritats */
.categoria-pesos {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.assignatura-row {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  padding: 0.75rem;
  background: #f9fafb;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
}

.assignatura-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.5rem;
}

.assignatura-header label {
  font-weight: 500;
  color: #374151;
  margin: 0;
  min-width: 150px;
}

.assignatura-auto {
  display: flex;
  align-items: center;
  gap: 0.25rem;
}

.assignatura-auto label {
  font-weight: normal !important;
  color: #6b7280;
  cursor: pointer;
}

.assignatura-controls {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.no-subst-list {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-top: 0.5rem;
}

/* Disponibles */
.disponibles-container {
  margin-top: 1rem;
}

.categoria-disponibles {
  margin-bottom: 1.5rem;
}

.categoria-disponibles h4 {
  font-size: 1.1rem;
  margin-bottom: 0.75rem;
  color: var(--primary-color);
  font-weight: 600;
}

.tipus-disponibles {
  margin-bottom: 1rem;
  padding-left: 1rem;
}

.tipus-label {
  font-weight: 500;
  margin-bottom: 0.5rem;
  color: var(--text-color-secondary);
}

.professors-list {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-top: 0.5rem;
}

.empty-message {
  text-align: center;
  padding: 1.5rem;
  color: var(--text-color-secondary);
  font-style: italic;
}

/* Fer que tota la capçalera del Panel sigui clicable */
:deep(.p-panel-header) {
  cursor: pointer;
  user-select: none;
}

:deep(.p-panel-header:hover) {
  background: rgba(0, 0, 0, 0.02);
}

/* Fer que el clic a qualsevol lloc del header dispari el toggle */
:deep(.p-panel-header .p-panel-title) {
  flex: 1;
  cursor: pointer;
}

:deep(.p-panel-header .p-panel-title):active {
  opacity: 0.7;
}
</style>
