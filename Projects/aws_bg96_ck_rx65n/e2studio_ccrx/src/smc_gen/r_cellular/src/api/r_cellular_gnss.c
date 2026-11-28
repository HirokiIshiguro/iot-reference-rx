/* BG96 GNSS start, location retrieval and stop. */
#include "cellular_private_api.h"
#include "cellular_freertos.h"
#include "at_command.h"

#if defined(CELLULAR_TARGET_BG96)
static e_cellular_err_t gnss_enter(st_cellular_ctrl_t * const p_ctrl)
{
    e_cellular_err_t ret = CELLULAR_SUCCESS;
    uint32_t preemption = cellular_interrupt_disable();
    if (NULL == p_ctrl)
    {
        ret = CELLULAR_ERR_PARAMETER;
    }
    else if (0 != (p_ctrl->running_api_count % 2))
    {
        ret = CELLULAR_ERR_OTHER_API_RUNNING;
    }
    else if (CELLULAR_SYSTEM_CLOSE == p_ctrl->system_state)
    {
        ret = CELLULAR_ERR_NOT_OPEN;
    }
    else
    {
        p_ctrl->running_api_count += 2;
    }
    cellular_interrupt_enable(preemption);
    if (CELLULAR_SUCCESS == ret)
    {
        if (CELLULAR_SEMAPHORE_SUCCESS != cellular_take_semaphore(p_ctrl->at_semaphore))
        {
            p_ctrl->running_api_count -= 2;
            ret = CELLULAR_ERR_OTHER_ATCOMMAND_RUNNING;
        }
    }
    return ret;
}

static void gnss_leave(st_cellular_ctrl_t * const p_ctrl)
{
    cellular_give_semaphore(p_ctrl->at_semaphore);
    p_ctrl->running_api_count -= 2;
}

static e_cellular_err_t gnss_command(st_cellular_ctrl_t * const p_ctrl, e_atc_list_t command)
{
    atc_generate(p_ctrl->sci_ctrl.atc_buff, gp_at_command[command], NULL);
    return cellular_execute_at_command(p_ctrl, p_ctrl->sci_ctrl.atc_timeout, ATC_RETURN_OK, command);
}

e_cellular_err_t R_CELLULAR_GnssStart(st_cellular_ctrl_t * const p_ctrl)
{
    e_cellular_err_t ret = gnss_enter(p_ctrl);
    int cmee = -1;
    if (CELLULAR_SUCCESS != ret) { return ret; }
    p_ctrl->recv_data = &cmee;
    ret = gnss_command(p_ctrl, ATC_GNSS_CMEE_QUERY);
    p_ctrl->recv_data = NULL;
    if ((CELLULAR_SUCCESS == ret) && ((cmee < 0) || (cmee > 2)))
    {
        ret = CELLULAR_ERR_MODULE_COM;
    }
    if ((CELLULAR_SUCCESS == ret) && (1 != cmee))
    {
        ret = gnss_command(p_ctrl, ATC_GNSS_CMEE_SET);
    }
    if (CELLULAR_SUCCESS == ret)
    {
        ret = gnss_command(p_ctrl, ATC_GNSS_START);
        /* Quectel GNSS AT Commands Manual, ch. 4: 504 = session ongoing. */
        if ((CELLULAR_ERR_MODULE_COM == ret) && (504 == p_ctrl->sci_ctrl.cme_error))
        {
            ret = CELLULAR_SUCCESS;
        }
    }
    gnss_leave(p_ctrl);
    return ret;
}

e_cellular_err_t R_CELLULAR_GnssStop(st_cellular_ctrl_t * const p_ctrl)
{
    e_cellular_err_t ret = gnss_enter(p_ctrl);
    if (CELLULAR_SUCCESS != ret) { return ret; }
    {
        int state = -1;
        p_ctrl->recv_data = &state;
        ret = gnss_command(p_ctrl, ATC_GNSS_STATE_QUERY);
        p_ctrl->recv_data = NULL;
        if ((CELLULAR_SUCCESS == ret) && (0 == state))
        {
            gnss_leave(p_ctrl);
            return CELLULAR_SUCCESS;
        }
        if ((CELLULAR_SUCCESS == ret) && (1 != state))
        {
            ret = CELLULAR_ERR_MODULE_COM;
        }
    }
    if (CELLULAR_SUCCESS == ret) { ret = gnss_command(p_ctrl, ATC_GNSS_STOP); }
    /* 505 = session not active. This is not a transport timeout. */
    if ((CELLULAR_ERR_MODULE_COM == ret) && (505 == p_ctrl->sci_ctrl.cme_error))
    {
        ret = CELLULAR_SUCCESS;
    }
    gnss_leave(p_ctrl);
    return ret;
}
/* Parse a complete +QGPSLOC line. Each token is bounded, and the output is
 * committed only after the whole line has passed structural validation. */
bool cellular_bg96_gnss_parse_location(const char * const line, st_cellular_gnss_location_t * const result)
{
    st_cellular_gnss_location_t tmp;
    st_cellular_gnss_field_t *fields[11];
    const char *p;
    unsigned int i;
    if ((NULL == line) || (NULL == result) || (0 != strncmp(line, "+QGPSLOC:", 9))) { return false; }
    memset(&tmp, 0, sizeof(tmp));
    fields[0]=&tmp.utc; fields[1]=&tmp.latitude; fields[2]=&tmp.longitude;
    fields[3]=&tmp.hdop; fields[4]=&tmp.altitude; fields[5]=&tmp.fix;
    fields[6]=&tmp.course; fields[7]=&tmp.speed_kmh; fields[8]=&tmp.speed_knots;
    fields[9]=&tmp.date; fields[10]=&tmp.satellites;
    p=line+9;
    while (' ' == *p) { p++; }
    for (i=0; i<11; i++)
    {
        size_t n=0;
        bool digit=false;
        bool dot=false;
        if (('-' == *p) && ((1 == i) || (2 == i) || (4 == i)))
        {
            fields[i]->value[n++]=*p++;
        }
        while ((*p != ',') && (*p != '\r') && (*p != '\n') && (*p != '\0'))
        {
            if (n >= sizeof(fields[i]->value)-1) { return false; }
            if (('.' == *p) && !dot && (i != 5) && (i != 9) && (i != 10)) { dot=true; }
            else if ((*p >= '0') && (*p <= '9')) { digit=true; }
            else { return false; }
            fields[i]->value[n++]=*p++;
        }
        if ((0 != n) && !digit) { return false; }
        fields[i]->valid = digit;
        if (i < 10)
        {
            if (',' != *p) { return false; }
            p++;
        }
        else if (',' == *p) { return false; }
    }
    if ((0 == tmp.utc.valid) || (0 == tmp.latitude.valid) || (0 == tmp.longitude.valid) ||
        (0 == tmp.fix.valid)) { return false; }
    tmp.state = CELLULAR_GNSS_FIXED;
    *result = tmp;
    return true;
}

e_cellular_err_t R_CELLULAR_GnssGetLocation(st_cellular_ctrl_t * const p_ctrl,
                                             st_cellular_gnss_location_t * const p_location)
{
    e_cellular_err_t ret;
    if (NULL == p_location) { return CELLULAR_ERR_PARAMETER; }
    ret = gnss_enter(p_ctrl);
    if (CELLULAR_SUCCESS != ret) { return ret; }
    memset(p_location, 0, sizeof(*p_location));
    p_location->state = CELLULAR_GNSS_STOPPED;
    p_ctrl->recv_data = p_location;
    ret = gnss_command(p_ctrl, ATC_GNSS_LOCATION);
    p_ctrl->recv_data = NULL;
    if (CELLULAR_ERR_MODULE_COM == ret)
    {
        if (516 == p_ctrl->sci_ctrl.cme_error)
        {
            p_location->state = CELLULAR_GNSS_NOT_FIXED;
            ret = CELLULAR_SUCCESS;
        }
        else if (505 == p_ctrl->sci_ctrl.cme_error)
        {
            p_location->state = CELLULAR_GNSS_STOPPED;
            ret = CELLULAR_SUCCESS;
        }
    }
    else if ((CELLULAR_SUCCESS == ret) && (CELLULAR_GNSS_FIXED != p_location->state))
    {
        ret = CELLULAR_ERR_MODULE_COM;
    }
    gnss_leave(p_ctrl);
    return ret;
}
#endif
