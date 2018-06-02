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
        if (!editorState.isEditingZone) {
            // Start a new rectangle
            this.setState({
                isCreatingZone: true,
                isEditingZone: false,
                startX: evt.nativeEvent.offsetX,
                startY: evt.nativeEvent.offsetY,
                dragX: evt.nativeEvent.offsetX,
                dragY: evt.nativeEvent.offsetY
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
                dragX: evt.nativeEvent.offsetX,
                dragY: evt.nativeEvent.offsetY
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
            newState.selectedZone.right = newState.selectedZone.left + newState.selectedZone.width;
            newState.selectedZone.bottom = newState.selectedZone.top + newState.selectedZone.height;

            const snapPoints = this.findSnapPoints(newState.selectedZone);
            if (snapPoints.left) {
                newState.selectedZone.left = snapPoints.left;
            }
            else if (snapPoints.right) {
                newState.selectedZone.left = snapPoints.right - newState.selectedZone.width;
            }

            if (snapPoints.top) {
                newState.selectedZone.top = snapPoints.top;
            }
            else if (snapPoints.bottom) {
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
            let zoneMinimumSize = 10;

            if (editorState.zoneResizingDirection === 'top')
            {
                yDisplacement = Math.min(yDisplacement, editorState.zoneStartHeight-zoneMinimumSize);
                newState.selectedZone.top = editorState.zoneStartY + yDisplacement;
                newState.selectedZone.height = editorState.zoneStartHeight - yDisplacement;
            }
            else if (editorState.zoneResizingDirection === 'bottom')
            {
                yDisplacement = Math.max(yDisplacement, -editorState.zoneStartHeight-zoneMinimumSize);
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
                xDisplacement = Math.max(xDisplacement, -editorState.zoneStartWidth-zoneMinimumSize);
                newState.selectedZone.right = editorState.zoneStartX + xDisplacement;
                newState.selectedZone.width = editorState.zoneStartWidth + xDisplacement;
            }

            const snapPoints = this.findSnapPoints(newState.selectedZone);
            console.log(snapPoints);
            if (editorState.zoneResizingDirection === 'top' && snapPoints.top)
            {
                const snapDisplacement = snapPoints.top - newState.selectedZone.top;
                newState.selectedZone.top = snapPoints.top;
                newState.selectedZone.height = newState.selectedZone.height - snapDisplacement;
            }
            else if (editorState.zoneResizingDirection === 'bottom' && snapPoints.bottom)
            {
                const snapDisplacement = snapPoints.bottom - newState.selectedZone.bottom;
                newState.selectedZone.bottom = snapPoints.bottom;
                newState.selectedZone.height = newState.selectedZone.height + snapDisplacement;
            }
            else if (editorState.zoneResizingDirection === 'left' && snapPoints.left)
            {
                const snapDisplacement = snapPoints.left - newState.selectedZone.left;
                newState.selectedZone.left = snapPoints.left;
                newState.selectedZone.width = newState.selectedZone.width - snapDisplacement;
            }
            else if (editorState.zoneResizingDirection === 'right' && snapPoints.right)
            {
                const snapDisplacement = snapPoints.right - newState.selectedZone.right;
                newState.selectedZone.right = snapPoints.right;
                newState.selectedZone.width = newState.selectedZone.width + snapDisplacement;
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
            if (zone !== snapZone) {
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
            const newState = {
                isCreatingZone: false,
                isEditingZone: true,
                dragX: evt.nativeEvent.offsetX,
                dragY: evt.nativeEvent.offsetY,
                editorX: evt.nativeEvent.offsetX,
                editorY: evt.nativeEvent.offsetY
            };

            // Start a new rectangle
            this.setState(newState, ()=>
            {
                const zones = this.props.zones;

                const newZone = this.computeZoneCoordinates(this.props.editorState);
                newZone.id = this.getNextZoneId();
                zones.push(newZone);
                this.updateZones(zones);
            });
        }
        else if (editorState.isDraggingZone)
        {
            this.setState({
                isDraggingZone: false,
                isEditingZone: true
            });
        }
        else if (editorState.isResizingZone)
        {
            this.setState({
                isResizingZone: false,
                isEditingZone: true
            });
        }
        else if (editorState.isEditingZone)
        {
            this.setState({
                isResizingZone: false,
                isEditingZone: false,
                selectedZone: null
            });
        }
    }


    computeZoneCoordinates(newState) {
        let width = Math.abs(newState.startX - newState.dragX);
        let height = Math.abs(newState.startY - newState.dragY);
        let left = Math.min(newState.startX, newState.dragX);
        let top = Math.min(newState.startY, newState.dragY);

        if (width < 10)
        {
            width += (10 - width);
        }
        if (height < 10)
        {
            height += (10 - height);
        }

        return {left, top, width, height, bottom: top+height, right: left+width};
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
            newState.newZone= this.computeZoneCoordinates(newState);
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

        return <div className="zone-editor">
            <div
                onMouseDown={this.onMouseDown.bind(this)}
                onMouseUp={this.onMouseUp.bind(this)}
                onMouseMove={this.onMouseMove.bind(this)}>
                <img src={this.props.src} draggable={false}/>
            </div>
            {
                editorState.isCreatingZone && editorState.newZone ?
                    <div className="zone-overlay" style={{
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
        if (event.button === 0)
        {
            this.props.onZoneMouseUp(event);
            event.preventDefault();
        }
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


