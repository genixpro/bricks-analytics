import React from 'react';
import {
    Grid,
    Popover,
    Row,
    Col,
    Panel,
    Button,
    FormControl,
    FormGroup,
    InputGroup,
    DropdownButton,
    Tab,
    Tabs,
    Nav,
    NavItem
} from 'react-bootstrap';
import Select from 'react-select'
import 'react-select/dist/react-select.css'
import _ from "underscore";
import classNames from 'classnames';


class ZoneEditor extends React.Component {
    constructor(props) {
        super(props);
    }

    componentDidMount() {

    }

    /**
     * Returns the next valid zone id
     */
    getNextZoneId() {
        let largest = 0;
        if (this.props.zones)
        {
            this.props.zones.forEach((zone) => {
                if (zone.id)
                {
                    largest = Math.max(zone.id, largest);
                }
            });
        }
        return largest + 1;
    }

    updateZones(zones) {
        if (this.props.updateZones) {
            this.props.updateZones(zones);
        }
    }


    /**
     * Triggered when this component is being removed from the screen
     */
    componentWillUnmount() {

    }

    onMouseDown(evt) {
        const editorState = this.props.editorState || {};
        if (editorState.isCreatingZone) {
            // treat like a mouse up
            this.onMouseUp(evt);
        }
        else if (!editorState.isEditingZone) {
            // Start a new rectangle
            this.setState({
                isCreatingZone: true,
                isEditingZone: false,
                zoneStartX: evt.nativeEvent.offsetX,
                zoneStartY: evt.nativeEvent.offsetY,
                startX: evt.nativeEvent.pageX,
                startY: evt.nativeEvent.pageY,
                dragX: evt.nativeEvent.pageX,
                dragY: evt.nativeEvent.pageY
            });
        }
        else {
            this.setState({
                isCreatingZone: false,
                isEditingZone: false,
                selectedZone: null
            })
        }
    }

    onMouseMove(evt) {
        const editorState = this.props.editorState || {};
        if (editorState.isCreatingZone && !editorState.isEditingZone) {
            // Start a new rectangle
            this.setState({
                dragX: evt.nativeEvent.pageX,
                dragY: evt.nativeEvent.pageY
            });
        }
        else if (editorState.isDraggingZone)
        {
            const newState = {
                dragX: evt.nativeEvent.pageX,
                dragY: evt.nativeEvent.pageY,
                selectedZone: editorState.selectedZone
            };

            newState.selectedZone.left = editorState.zoneStartX + (newState.dragX - editorState.startX);
            newState.selectedZone.top = editorState.zoneStartY + (newState.dragY - editorState.startY);

            // Make sure the zone stays within bounds
            const maxWidth = document.getElementById('zone-editor-image').getBoundingClientRect().width;
            const maxHeight = document.getElementById('zone-editor-image').getBoundingClientRect().height;

            newState.selectedZone.left = Math.max(newState.selectedZone.left, 0);
            newState.selectedZone.left = Math.min(newState.selectedZone.left, maxWidth - newState.selectedZone.width);

            newState.selectedZone.top = Math.max(newState.selectedZone.top, 0);
            newState.selectedZone.top = Math.min(newState.selectedZone.top, maxHeight - newState.selectedZone.height);

            // Compute the bottom
            newState.selectedZone.right = newState.selectedZone.left + newState.selectedZone.width;
            newState.selectedZone.bottom = newState.selectedZone.top + newState.selectedZone.height;

            // Snap to any other zones as needed
            const snapPoints = this.findSnapPoints(newState.selectedZone);
            if (!_.isUndefined(snapPoints.left)) {
                newState.selectedZone.left = snapPoints.left;
            }
            else if (!_.isUndefined(snapPoints.right)) {
                newState.selectedZone.left = snapPoints.right - newState.selectedZone.width;
            }

            if (!_.isUndefined(snapPoints.top)) {
                newState.selectedZone.top = snapPoints.top;
            }
            else if (!_.isUndefined(snapPoints.bottom)) {
                newState.selectedZone.top = snapPoints.bottom - newState.selectedZone.height;
            }

            newState.selectedZone.right = newState.selectedZone.left + newState.selectedZone.width;
            newState.selectedZone.bottom = newState.selectedZone.top + newState.selectedZone.height;

            this.setState(newState);
        }
        else if (editorState.isResizingZone)
        {
            const newState = {
                dragX: evt.nativeEvent.pageX,
                dragY: evt.nativeEvent.pageY,
                selectedZone: editorState.selectedZone
            };

            let xDisplacement = (newState.dragX - editorState.startX);
            let yDisplacement = (newState.dragY - editorState.startY);
            let zoneMinimumSize = 20;

            if (editorState.zoneResizingDirection === 'top')
            {
                yDisplacement = Math.min(yDisplacement, editorState.zoneStartHeight-zoneMinimumSize);
                newState.selectedZone.top = editorState.zoneStartY + yDisplacement;
                newState.selectedZone.height = editorState.zoneStartHeight - yDisplacement;
            }
            else if (editorState.zoneResizingDirection === 'bottom')
            {
                yDisplacement = Math.max(yDisplacement, -editorState.zoneStartHeight+zoneMinimumSize);
                newState.selectedZone.bottom = editorState.zoneStartY + yDisplacement;
                newState.selectedZone.height = editorState.zoneStartHeight + yDisplacement;
            }
            else if (editorState.zoneResizingDirection === 'left')
            {
                xDisplacement = Math.min(xDisplacement, editorState.zoneStartWidth-zoneMinimumSize);
                newState.selectedZone.left = editorState.zoneStartX + xDisplacement;
                newState.selectedZone.width = editorState.zoneStartWidth - xDisplacement;
            }
            else if (editorState.zoneResizingDirection === 'right')
            {
                xDisplacement = Math.max(xDisplacement, -editorState.zoneStartWidth+zoneMinimumSize);
                newState.selectedZone.right = editorState.zoneStartX + xDisplacement;
                newState.selectedZone.width = editorState.zoneStartWidth + xDisplacement;
            }

            const snapPoints = this.findSnapPoints(newState.selectedZone);

            if (editorState.zoneResizingDirection === 'top' && !_.isUndefined(snapPoints.top))
            {
                const snapDisplacement = snapPoints.top - newState.selectedZone.top;
                newState.selectedZone.height = newState.selectedZone.height - snapDisplacement;
                newState.selectedZone.top = snapPoints.top;
            }
            else if (editorState.zoneResizingDirection === 'bottom' && !_.isUndefined(snapPoints.bottom))
            {
                const snapDisplacement = snapPoints.bottom - newState.selectedZone.bottom;
                newState.selectedZone.height = newState.selectedZone.height + snapDisplacement;
                newState.selectedZone.bottom = snapPoints.bottom;
            }
            else if (editorState.zoneResizingDirection === 'left' && !_.isUndefined(snapPoints.left))
            {
                const snapDisplacement = snapPoints.left - newState.selectedZone.left;
                newState.selectedZone.width = newState.selectedZone.width - snapDisplacement;
                newState.selectedZone.left = snapPoints.left;
            }
            else if (editorState.zoneResizingDirection === 'right' && !_.isUndefined(snapPoints.right))
            {
                const snapDisplacement = snapPoints.right - newState.selectedZone.right;
                newState.selectedZone.width = newState.selectedZone.width + snapDisplacement;
                newState.selectedZone.right = snapPoints.right;
            }

            this.setState(newState);
        }
    }

    findSnapPoints(snapZone)
    {
        const editorState = this.props.editorState || {};
        const snapDistance = 20;
        const snapPerpendicularMaxDistance = 30;

        // Go through all the other zones, determine if there are any snap points
        let leftSnapPoints = [];
        let topSnapPoints = [];
        let rightSnapPoints = [];
        let bottomSnapPoints = [];
        this.props.zones.forEach((zone) =>
        {
            if (zone.id !== snapZone.id) {
                const hasVerticalOverlap = (zone.top > snapZone.top && zone.top < snapZone.bottom)
                    || (zone.bottom > snapZone.top && zone.bottom < snapZone.bottom)
                    || (snapZone.top > zone.top && snapZone.top < zone.bottom)
                    || (snapZone.bottom > zone.top && snapZone.bottom < zone.bottom);

                const hasHorizontalOverlap = (zone.left > snapZone.left && zone.left < snapZone.right)
                    || (zone.right > snapZone.left && zone.right < snapZone.right)
                    || (snapZone.left > zone.left && snapZone.left < zone.right)
                    || (snapZone.right > zone.left && snapZone.right < zone.right);

                const minimumHorizontalDistance = Math.min(
                    Math.abs(snapZone.left - zone.left),
                    Math.abs(snapZone.left - zone.right),
                    Math.abs(snapZone.right - zone.left),
                    Math.abs(snapZone.right - zone.right)
                );

                const minimumVerticalDistance = Math.min(
                    Math.abs(snapZone.top - zone.top),
                    Math.abs(snapZone.top - zone.bottom),
                    Math.abs(snapZone.bottom - zone.top),
                    Math.abs(snapZone.bottom - zone.bottom)
                );

                const allowVerticalSnap = hasHorizontalOverlap || minimumHorizontalDistance < snapPerpendicularMaxDistance;
                const allowHorizontalSnap = hasVerticalOverlap || minimumVerticalDistance < snapPerpendicularMaxDistance;

                if (Math.abs(snapZone.left - zone.left) < snapDistance && allowHorizontalSnap)
                {
                    leftSnapPoints.push({
                        left: zone.left,
                        distance: Math.abs(snapZone.left - zone.left)
                    })
                }
                if (Math.abs(snapZone.left - zone.right) < snapDistance && allowHorizontalSnap)
                {
                    leftSnapPoints.push({
                        left: zone.right,
                        distance: Math.abs(snapZone.left - zone.right)
                    })
                }
                if (Math.abs(snapZone.right - zone.left) < snapDistance && allowHorizontalSnap)
                {
                    rightSnapPoints.push({
                        right: zone.left,
                        distance: Math.abs(snapZone.right - zone.left)
                    })
                }
                if (Math.abs(snapZone.right - zone.right) < snapDistance && allowHorizontalSnap)
                {
                    rightSnapPoints.push({
                        right: zone.right,
                        distance: Math.abs(snapZone.right - zone.right)
                    })
                }
                if (Math.abs(snapZone.top - zone.top) < snapDistance && allowVerticalSnap)
                {
                    topSnapPoints.push({
                        top: zone.top,
                        distance: Math.abs(snapZone.top - zone.top)
                    })
                }
                if (Math.abs(snapZone.top - zone.bottom) < snapDistance && allowVerticalSnap)
                {
                    topSnapPoints.push({
                        top: zone.bottom,
                        distance: Math.abs(snapZone.top - zone.bottom)
                    })
                }
                if (Math.abs(snapZone.bottom - zone.top) < snapDistance && allowVerticalSnap)
                {
                    bottomSnapPoints.push({
                        bottom: zone.top,
                        distance: Math.abs(snapZone.bottom - zone.top)
                    })
                }
                if (Math.abs(snapZone.bottom - zone.bottom) < snapDistance && allowVerticalSnap)
                {
                    bottomSnapPoints.push({
                        bottom: zone.bottom,
                        distance: Math.abs(snapZone.bottom - zone.bottom)
                    })
                }
            }
        });

        // Add in snap points for the outer edges of the map
        const maxWidth = document.getElementById('zone-editor-image').getBoundingClientRect().width;
        const maxHeight = document.getElementById('zone-editor-image').getBoundingClientRect().height;

        if (snapZone.left < snapDistance)
        {
            leftSnapPoints.push({
                left: 0,
                distance: snapZone.left
            })
        }
        if (snapZone.top < snapDistance)
        {
            topSnapPoints.push({
                top: 0,
                distance: snapZone.top
            })
        }
        if ((maxWidth - snapZone.right) < snapDistance)
        {
            rightSnapPoints.push({
                right: maxWidth,
                distance: (maxWidth - snapZone.right)
            })
        }
        if ((maxHeight - snapZone.bottom) < snapDistance)
        {
            bottomSnapPoints.push({
                bottom: maxHeight,
                distance: (maxHeight - snapZone.bottom)
            })
        }

        // Now we choose the best snap in each category
        const bestLeftSnap = _.min(leftSnapPoints, (snap) => snap.distance);
        const bestRightSnap = _.min(rightSnapPoints, (snap) => snap.distance);
        const bestTopSnap = _.min(topSnapPoints, (snap) => snap.distance);
        const bestBottomSnap = _.min(bottomSnapPoints, (snap) => snap.distance);


        const result = {};
        if (bestLeftSnap)
        {
            result.left = bestLeftSnap.left;
        }
        if (bestRightSnap)
        {
            result.right = bestRightSnap.right;
        }
        if (bestTopSnap)
        {
            result.top = bestTopSnap.top;
        }
        if (bestBottomSnap)
        {
            result.bottom = bestBottomSnap.bottom;
        }

        return result;
    }


    onMouseUp(evt) {
        const editorState = this.props.editorState || {};
        if (editorState.isCreatingZone && !editorState.isEditingZone) {
            const newState = editorState;
            newState.dragX = evt.nativeEvent.pageX;
            newState.dragY = evt.nativeEvent.pageY;
            newState.isCreatingZone = false;
            newState.isEditingZone = true;

            const zones = this.props.zones;
            const newZone = this.computeNewZoneCoordinates(this.props.editorState);
            newZone.id = this.getNextZoneId();
            zones.push(newZone);
            this.updateZones(zones);

            newState.selectedZone = newZone;

            // Start a new rectangle
            this.setState(newState);
        }
        else if (editorState.isDraggingZone)
        {
            // Copy values into official record
            const zone = _.findWhere(this.props.zones, {id: this.props.editorState.selectedZone.id});
            Object.keys(zone).forEach((key) => zone[key] = this.props.editorState.selectedZone[key]);
            this.updateZones(this.props.zones);

            this.setState({
                isDraggingZone: false,
                isEditingZone: true,
            });
        }
        else if (editorState.isResizingZone)
        {
            // Copy values into official record
            const zone = _.findWhere(this.props.zones, {id: this.props.editorState.selectedZone.id});
            Object.keys(zone).forEach((key) => zone[key] = this.props.editorState.selectedZone[key]);
            this.updateZones(this.props.zones);

            this.setState({
                isResizingZone: false,
                isEditingZone: true
            });
        }
        else if (editorState.isEditingZone)
        {
            // Copy values into official record
            const zone = _.findWhere(this.props.zones, {id: this.props.editorState.selectedZone.id});
            Object.keys(zone).forEach((key) => zone[key] = this.props.editorState.selectedZone[key]);
            this.updateZones(this.props.zones);

            this.setState({
                isResizingZone: false,
                isEditingZone: false,
                selectedZone: null
            });
        }
    }


    computeNewZoneCoordinates(newState) {
        let width = Math.abs(newState.startX - newState.dragX);
        let height = Math.abs(newState.startY - newState.dragY);
        let left = Math.min(newState.zoneStartX, newState.zoneStartX + (newState.dragX - newState.startX));
        let top = Math.min(newState.zoneStartY, newState.zoneStartY + (newState.dragY - newState.startY));

        // Make sure the zone stays within bounds
        const maxWidth = document.getElementById('zone-editor-image').getBoundingClientRect().width;
        const maxHeight = document.getElementById('zone-editor-image').getBoundingClientRect().height;

        width = Math.min(width, maxWidth - left);
        height = Math.min(height, maxHeight - top);

        if (width < 20)
        {
            width = 20;
        }
        if (height < 20)
        {
            height = 20;
        }

        const newZone = {id: 'new', left, top, width, height, bottom: top+height, right: left+width};

        // Snap to any other zones as needed
        const snapPoints = this.findSnapPoints(newZone);

        if (!_.isUndefined(snapPoints.left)) {
            const snapDisplacement = snapPoints.left - newZone.left;
            newZone.width = newZone.width - snapDisplacement;
            newZone.left = snapPoints.left;
        }
        else if (!_.isUndefined(snapPoints.right)) {
            const snapDisplacement = snapPoints.right - newZone.right;
            newZone.width = newZone.width + snapDisplacement;
            newZone.left = snapPoints.right - newZone.width;
        }

        if (!_.isUndefined(snapPoints.top)) {
            const snapDisplacement = snapPoints.top - newZone.top;
            newZone.height = newZone.height - snapDisplacement;
            newZone.top = snapPoints.top;
        }
        else if (!_.isUndefined(snapPoints.bottom)) {
            const snapDisplacement = snapPoints.bottom - newZone.bottom;
            newZone.height = newZone.height + snapDisplacement;
            newZone.top = snapPoints.bottom - newZone.height;
        }

        newZone.right = newZone.left + newZone.width;
        newZone.bottom = newZone.top + newZone.height;

        return newZone;
    }



    onChangeZoneType(newType, event) {
        this.setState({
            zoneType: newType
        });
        event.preventDefault();
    }

    preventEventHandler(e) {
        e.preventDefault();
    }


    onZoneMouseDown(zone, event) {
        this.setState({
            isDraggingZone: true,
            selectedZone: zone,
            startX: event.nativeEvent.pageX,
            startY: event.nativeEvent.pageY,
            zoneStartX: zone.left,
            zoneStartY: zone.top,
            zoneStartWidth: zone.width,
            zoneStartHeight: zone.height
        })
    }

    onZoneResizeMouseDown(zone, direction, event) {
        const newState = {
            isResizingZone: true,
            zoneResizingDirection: direction,
            selectedZone: zone,
            startX: event.nativeEvent.pageX,
            startY: event.nativeEvent.pageY,
            zoneStartX: zone.left,
            zoneStartY: zone.top,
            zoneStartWidth: zone.width,
            zoneStartHeight: zone.height
        };

        if (direction === 'top')
        {
            newState.zoneStartY = zone.top;
        }
        else if (direction === 'left')
        {
            newState.zoneStartX = zone.left;
        }
        else if (direction === 'right')
        {
            newState.zoneStartX = zone.right;
        }
        else if (direction === 'bottom')
        {
            newState.zoneStartY = zone.bottom;
        }

        this.setState(newState)
    }

    deleteSelectedZone()
    {
        const editorState = this.props.editorState || {};
        const newZones = _.filter(this.props.zones, (zone) => zone.id !== editorState.selectedZone.id);
        this.updateZones(newZones);
        this.setState({
            isEditingZone: false,
            selectedZone: null
        })
    }

    zoneNameChanged(event)
    {
        const editorState = this.props.editorState || {};
        const zone = _.findWhere(this.props.zones, {id: editorState.selectedZone.id});
        zone.name = event.target.value;
        this.updateZones(zones);
        this.setState({selectedZone: zone})
    }

    // Override setState
    setState(newState, callback) {
        const editorState = this.props.editorState || {};
        newState = _.extend({}, editorState, newState);
        if (newState.dragX) {
            newState.newZone= this.computeNewZoneCoordinates(newState);
        }
        else {
            newState.newZone= null;
        }

        this.props.updateEditorState(newState, callback);
    }

    render() {
        const options = [
            {value: 'entry', label: 'Entry & Exit'},
            {value: 'checkout', label: 'Checkout'},
            {value: 'shelving', label: 'Shelving'},
            {value: 'isle', label: 'Isle'}
        ];
        
        const editorState = this.props.editorState || {};

        return <div id={'zone-editor'} className="zone-editor">
            <div
                onMouseDown={this.onMouseDown.bind(this)}
                onMouseUp={this.onMouseUp.bind(this)}
                onMouseMove={this.onMouseMove.bind(this)}>
                <img id={"zone-editor-image"} src={this.props.src} draggable={false}/>
            </div>
            {
                editorState.isCreatingZone && editorState.newZone ?
                    <div className="zone-overlay new-zone" style={{
                        "left": editorState.newZone.left,
                        "top": editorState.newZone.top,
                        "height": editorState.newZone.height,
                        "width": editorState.newZone.width
                    }}/>
                    : null
            }
            {
                this.props.zones ?
                    this.props.zones.map((zone) =>
                        zone != null ?
                            <Zone
                                key={zone.id}
                                zone={zone}
                                onZoneMouseDown={this.onZoneMouseDown.bind(this)}
                                onZoneMouseMove={this.onMouseMove.bind(this)}
                                onZoneMouseUp={this.onMouseUp.bind(this)}
                                onZoneResizeMouseDown={this.onZoneResizeMouseDown.bind(this)}
                                selected={editorState.selectedZone === zone}
                            />
                        : null
                    )
                : null
            }
            {
                editorState.selectedZone && editorState.isEditingZone ?
                    <Popover
                        id="zone-popover"
                        placement="right"
                        positionLeft={editorState.selectedZone.left + editorState.selectedZone.width}
                        positionTop={editorState.selectedZone.top}
                        title="Zone Details"
                    >
                        <FormControl type="text" placeholder="Name" className="form-control" value={editorState.selectedZone.name} onChange={this.zoneNameChanged.bind(this)}/>
                        <br/>
                        <Select
                            options={options}
                            value={editorState.zoneType}
                            onChange={this.onChangeZoneType.bind(this)}
                            style={{"width": "200px"}}
                        />
                        <br/>
                        <br/>
                        <Button
                            onClick={this.deleteSelectedZone.bind(this)}
                            bsStyle={"danger"}
                        >Delete</Button>
                        <br/>
                    </Popover>
                    : null
            }
        </div>;
    }
}

class Zone  extends React.Component {

    onResizeMouseDown(direction, event)
    {
        if (event.button === 0) {
            this.props.onZoneResizeMouseDown(this.props.zone, direction, event);
            event.preventDefault();
        }
    }

    onBodyMouseDown(event)
    {
        if (event.button === 0)
        {
            this.props.onZoneMouseDown(this.props.zone, event);
            event.preventDefault();
        }
    }

    onMouseMove(event)
    {
        this.props.onZoneMouseMove(event);
    }

    onMouseUp(event)
    {
        this.props.onZoneMouseUp(event);
    }



    render() {
        return <div className= {classNames({'zone-overlay': true, 'selected': this.props.selected})} style={{
                "left": this.props.zone.left,
                "top": this.props.zone.top,
                "height": this.props.zone.height,
                "width": this.props.zone.width,
            }}
            onMouseMove={this.onMouseMove.bind(this)}
            onMouseUp={this.onMouseUp.bind(this)}
            >

            <div className="zone-body-drag-area"
                 onMouseDown={this.onBodyMouseDown.bind(this)} />
            <div className="zone-top-handle"  onMouseDown={this.onResizeMouseDown.bind(this, 'top')}/>
            <div className="zone-left-handle" onMouseDown={this.onResizeMouseDown.bind(this, 'left')}/>
            <div className="zone-right-handle" onMouseDown={this.onResizeMouseDown.bind(this, 'right')}/>
            <div className="zone-bottom-handle" onMouseDown={this.onResizeMouseDown.bind(this, 'bottom')}/>
        </div>
    }
}

export default ZoneEditor


