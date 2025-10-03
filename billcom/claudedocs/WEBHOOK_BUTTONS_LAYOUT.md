# Webhook Buttons - Improved Layout

## New Organization

Los botones de webhook ahora están organizados en una **button box** visual con iconos,
similar a los botones de estadísticas de Odoo.

### Visual Layout

```
┌─────────────────────────────────────────────────────────────┐
│  Webhook Actions                                            │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐
│  │    🔌    │  │    🔗    │  │    🧪    │  │    🔄    │  │    📋    │
│  │Subscribe │  │Unsubscribe│ │   Test   │  │   Sync   │  │View All  │
│  │          │  │          │  │  Webhook │  │  Status  │  │          │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  └──────────┘
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Button Details

### 🔌 Subscribe

- **Icon**: `fa-plug`
- **Class**: `oe_stat_button btn-primary` (destacado en azul)
- **Visible**: Cuando `webhook_subscription_state != 'subscribed'`
- **Acción**: Crear suscripción a webhooks

### 🔗 Unsubscribe

- **Icon**: `fa-unlink`
- **Class**: `oe_stat_button btn-warning` (naranja/amarillo)
- **Visible**: Cuando `webhook_subscription_state == 'subscribed'`
- **Confirmación**: "Are you sure you want to unsubscribe from webhooks?"
- **Acción**: Eliminar suscripción

### 🧪 Test Webhook

- **Icon**: `fa-flask`
- **Class**: `oe_stat_button` (estilo estándar)
- **Visible**: Cuando `webhook_subscription_state == 'subscribed'`
- **Acción**: Probar conexión de webhook

### 🔄 Sync Status

- **Icon**: `fa-refresh`
- **Class**: `oe_stat_button` (estilo estándar)
- **Visible**: Siempre (cuando webhooks están habilitados)
- **Acción**: Sincronizar estado de suscripción desde Bill.com

### 📋 View All

- **Icon**: `fa-list`
- **Class**: `oe_stat_button` (estilo estándar)
- **Visible**: Siempre (cuando webhooks están habilitados)
- **Acción**: Ver todas las suscripciones en Bill.com

## Benefits vs Previous Layout

### Antes ❌

```
┌─────────────────────────────────┐
│ [Subscribe to Webhooks]         │  <- Botón vertical en grupo
│ [Unsubscribe from Webhooks]     │
│ [Test Webhook]                  │
│ [Sync Subscription Status]      │
│ [View All Subscriptions]        │
└─────────────────────────────────┘
```

**Problemas:**

- Botones apilados verticalmente (ocupa mucho espacio vertical)
- Sin iconos visuales
- Texto largo en cada botón
- Menos intuitivo

### Ahora ✅

```
┌─────────────────────────────────────────────────────────────┐
│  [🔌] [🔗] [🧪] [🔄] [📋]   <- Botones horizontales        │
└─────────────────────────────────────────────────────────────┘
```

**Mejoras:**

- ✅ Botones en línea horizontal (ahorra espacio vertical)
- ✅ Iconos intuitivos para cada acción
- ✅ Estilo consistente con Odoo (oe_stat_button)
- ✅ Visibilidad contextual (subscribe/unsubscribe según estado)
- ✅ Colores diferenciados (azul=primario, naranja=advertencia)
- ✅ Más compacto y profesional

## Technical Implementation

### HTML Structure

```xml
<div attrs="{'invisible': [('enable_webhooks', '=', False)]}" class="mt16">
    <separator string="Webhook Actions" />
    <div class="row mt8">
        <div class="col-12">
            <div class="oe_button_box" name="webhook_actions">
                <!-- Stat buttons here -->
            </div>
        </div>
    </div>
</div>
```

### Button Template

```xml
<button
  name="button_name"
  type="object"
  string="Label"
  class="oe_stat_button [btn-primary|btn-warning]"
  icon="fa-icon-name"
  attrs="{'invisible': [...]}"
/>
```

## User Experience Flow

### Flujo: No Suscrito → Suscrito

1. Usuario ve botón **🔌 Subscribe** (azul destacado)
2. Click en Subscribe → Crea suscripción
3. Botón cambia a **🔗 Unsubscribe** (naranja)
4. Aparecen **🧪 Test** para probar
5. **🔄 Sync** y **📋 View All** siempre disponibles

### Flujo: Suscrito → Probar

1. Usuario ve estado "Subscribed" (badge verde)
2. Click en **🧪 Test Webhook** → Envía webhook de prueba
3. Verifica en logs que llegó correctamente

### Flujo: Verificar Estado

1. Click en **🔄 Sync Status** → Consulta Bill.com
2. Sistema actualiza estado de suscripción
3. Si hay cambios, muestra notificación

### Flujo: Ver Todas las Suscripciones

1. Click en **📋 View All** → Abre wizard/ventana
2. Muestra lista de todas las suscripciones en Bill.com
3. Usuario puede identificar duplicados u orphaned subscriptions

## Visual Consistency

Los botones ahora siguen el patrón de Odoo **oe_stat_button**:

- Usado comúnmente en smart buttons del formulario
- Diseño rectangular con icono y texto
- Disposición horizontal en button box
- Responsive y adaptable

## Space Optimization

### Espacio Vertical Ahorrado

- **Antes**: ~150px (5 botones × 30px c/u)
- **Ahora**: ~50px (1 línea de botones)
- **Ahorro**: ~100px (~66% menos espacio)

### Mejor Uso del Espacio Horizontal

- Botones distribuidos uniformemente
- Aprovecha ancho completo de la pantalla
- Más botones visibles sin scroll

## Accessibility

- ✅ Iconos FontAwesome reconocibles
- ✅ Texto descriptivo en cada botón
- ✅ Colores con suficiente contraste
- ✅ Estados claros (visible/invisible)
- ✅ Confirmación en acciones destructivas (unsubscribe)

## Maintenance

Para agregar un nuevo botón webhook:

```xml
<button
  name="button_new_action"
  type="object"
  string="New Action"
  class="oe_stat_button"
  icon="fa-new-icon"
  attrs="{'invisible': [('condition', '=', value)]}"
/>
```

Simplemente agrégalo dentro del `<div class="oe_button_box">` y se alineará
automáticamente.
