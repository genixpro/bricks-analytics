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

    componentDidMount() {
        const editorState = this.props.editorState || {};

        const maxWidth = document.getElementById('zone-editor-image').getBoundingClientRect().width;
        const maxHeight = document.getElementById('zone-editor-image').getBoundingClientRect().height;

        if (maxHeight !== editorState.imageMaxHeight || maxWidth !== editorState.imageMaxWidth)
        {
            this.setState({
                imageMaxWidth: maxWidth,
                imageMaxHeight: maxHeight
            })
        }
    }

    onMouseDown(evt) {
        const editorState = this.props.editorState || {};

        const maxWidth = document.getElementById('zone-editor-image').getBoundingClientRect().width;
        const maxHeight = document.getElementById('zone-editor-image').getBoundingClientRect().height;

        if (editorState.isCreatingZone) {
            // treat like a mouse up
            this.onMouseUp(evt);
        }
        else if (!editorState.isEditingZone) {
            // Start a new rectangle
            this.setState({
                isCreatingZone: true,
                isEditingZone: false,
                zoneStartX: evt.nativeEvent.offsetX / maxWidth,
                zoneStartY: evt.nativeEvent.offsetY / maxHeight,
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

        const maxWidth = document.getElementById('zone-editor-image').getBoundingClientRect().width;
        const maxHeight = document.getElementById('zone-editor-image').getBoundingClientRect().height;

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

            newState.selectedZone.left = editorState.zoneStartX + (newState.dragX - editorState.startX) / maxWidth;
            newState.selectedZone.top = editorState.zoneStartY + (newState.dragY - editorState.startY) / maxHeight;

            // Make sure the zone stays within bounds
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

            const maxWidth = document.getElementById('zone-editor-image').getBoundingClientRect().width;
            const maxHeight = document.getElementById('zone-editor-image').getBoundingClientRect().height;

            let xDisplacement = (newState.dragX - editorState.startX) / maxWidth;
            let yDisplacement = (newState.dragY - editorState.startY) / maxHeight;
            let zoneMinimumWidth = 20.0 / maxWidth;
            let zoneMinimumHeight = 20.0 / maxHeight;

            if (editorState.zoneResizingDirection === 'top')
            {
                yDisplacement = Math.min(yDisplacement, editorState.zoneStartHeight-zoneMinimumHeight);
                newState.selectedZone.top = editorState.zoneStartY + yDisplacement;
                newState.selectedZone.height = editorState.zoneStartHeight - yDisplacement;
            }
            else if (editorState.zoneResizingDirection === 'bottom')
            {
                yDisplacement = Math.max(yDisplacement, -editorState.zoneStartHeight+zoneMinimumHeight);
                newState.selectedZone.bottom = editorState.zoneStartY + yDisplacement;
                newState.selectedZone.height = editorState.zoneStartHeight + yDisplacement;
            }
            else if (editorState.zoneResizingDirection === 'left')
            {
                xDisplacement = Math.min(xDisplacement, editorState.zoneStartWidth-zoneMinimumWidth);
                newState.selectedZone.left = editorState.zoneStartX + xDisplacement;
                newState.selectedZone.width = editorState.zoneStartWidth - xDisplacement;
            }
            else if (editorState.zoneResizingDirection === 'right')
            {
                xDisplacement = Math.max(xDisplacement, -editorState.zoneStartWidth+zoneMinimumWidth);
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
        const maxWidth = document.getElementById('zone-editor-image').getBoundingClientRect().width;
        const maxHeight = document.getElementById('zone-editor-image').getBoundingClientRect().height;

        const snapWidth = 20 / maxWidth;
        const snapHeight = 20 / maxHeight;
        const snapPerpendicularMaxWidth = 30 / maxWidth;
        const snapPerpendicularMaxHeight = 30 / maxHeight;

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

                const allowVerticalSnap = hasHorizontalOverlap || minimumHorizontalDistance < snapPerpendicularMaxWidth;
                const allowHorizontalSnap = hasVerticalOverlap || minimumVerticalDistance < snapPerpendicularMaxHeight;

                if (Math.abs(snapZone.left - zone.left) < snapWidth && allowHorizontalSnap)
                {
                    leftSnapPoints.push({
                        left: zone.left,
                        distance: Math.abs(snapZone.left - zone.left)
                    })
                }
                if (Math.abs(snapZone.left - zone.right) < snapWidth && allowHorizontalSnap)
                {
                    leftSnapPoints.push({
                        left: zone.right,
                        distance: Math.abs(snapZone.left - zone.right)
                    })
                }
                if (Math.abs(snapZone.right - zone.left) < snapWidth && allowHorizontalSnap)
                {
                    rightSnapPoints.push({
                        right: zone.left,
                        distance: Math.abs(snapZone.right - zone.left)
                    })
                }
                if (Math.abs(snapZone.right - zone.right) < snapWidth && allowHorizontalSnap)
                {
                    rightSnapPoints.push({
                        right: zone.right,
                        distance: Math.abs(snapZone.right - zone.right)
                    })
                }
                if (Math.abs(snapZone.top - zone.top) < snapHeight && allowVerticalSnap)
                {
                    topSnapPoints.push({
                        top: zone.top,
                        distance: Math.abs(snapZone.top - zone.top)
                    })
                }
                if (Math.abs(snapZone.top - zone.bottom) < snapHeight && allowVerticalSnap)
                {
                    topSnapPoints.push({
                        top: zone.bottom,
                        distance: Math.abs(snapZone.top - zone.bottom)
                    })
                }
                if (Math.abs(snapZone.bottom - zone.top) < snapHeight && allowVerticalSnap)
                {
                    bottomSnapPoints.push({
                        bottom: zone.top,
                        distance: Math.abs(snapZone.bottom - zone.top)
                    })
                }
                if (Math.abs(snapZone.bottom - zone.bottom) < snapHeight && allowVerticalSnap)
                {
                    bottomSnapPoints.push({
                        bottom: zone.bottom,
                        distance: Math.abs(snapZone.bottom - zone.bottom)
                    })
                }
            }
        });

        if (snapZone.left < snapWidth)
        {
            leftSnapPoints.push({
                left: 0,
                distance: snapZone.left
            })
        }
        if (snapZone.top < snapHeight)
        {
            topSnapPoints.push({
                top: 0,
                distance: snapZone.top
            })
        }
        if ((1.0 - snapZone.right) < snapWidth)
        {
            rightSnapPoints.push({
                right: 1.0,
                distance: (1.0 - snapZone.right)
            })
        }
        if ((1.0 - snapZone.bottom) < snapHeight)
        {
            bottomSnapPoints.push({
                bottom: 1.0,
                distance: (1.0 - snapZone.bottom)
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
        // Make sure the zone stays within bounds
        const maxWidth = document.getElementById('zone-editor-image').getBoundingClientRect().width;
        const maxHeight = document.getElementById('zone-editor-image').getBoundingClientRect().height;

        const minWidth = 20 / maxWidth;
        const minHeight = 20 / maxHeight;

        let width = Math.abs(newState.startX - newState.dragX) / maxWidth;
        let height = Math.abs(newState.startY - newState.dragY) / maxHeight;
        let left = Math.min(newState.zoneStartX, newState.zoneStartX + (newState.dragX - newState.startX) / maxWidth);
        let top = Math.min(newState.zoneStartY, newState.zoneStartY + (newState.dragY - newState.startY) / maxHeight);

        width = Math.min(width, maxWidth - left);
        height = Math.min(height, maxHeight - top);

        if (width < minWidth)
        {
            width = minWidth;
        }
        if (height < minHeight)
        {
            height = minHeight;
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
                        "left": (editorState.newZone.left * 100).toFixed(2) + "%",
                        "top": (editorState.newZone.top * 100).toFixed(2) + "%",
                        "height": (editorState.newZone.height * 100).toFixed(2) + "%",
                        "width": (editorState.newZone.width * 100).toFixed(2) + "%"
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
                editorState.selectedZone && editorState.isEditingZone && editorState.imageMaxWidth && editorState.imageMaxHeight ?
                    <Popover
                        id="zone-popover"
                        placement="right"
                        positionLeft={(editorState.selectedZone.left + editorState.selectedZone.width) * editorState.imageMaxWidth}
                        positionTop={editorState.selectedZone.top* editorState.imageMaxHeight}
                        title={"Zone " + editorState.selectedZone.id + " Details"}
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
                "left": (this.props.zone.left * 100).toFixed(3) + "%",
                "top": (this.props.zone.top * 100).toFixed(3) + "%",
                "height": (this.props.zone.height * 100).toFixed(3) + "%",
                "width": (this.props.zone.width * 100).toFixed(3) + "%",
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

            <div className="zone-info">
                <p>zone-{this.props.zone.id}</p>
                {
                    this.props.zone.name ?
                        <p>{this.props.zone.name}</p>
                        : null
                }
                {
                    this.props.zone.zoneType ?
                        <p>{this.props.zone.zoneType}</p>
                        : null
                }
            </div>
        </div>
    }
}

export default ZoneEditor


